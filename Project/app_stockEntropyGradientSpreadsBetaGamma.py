#pip install pandas numpy pyodbc
import pandas as pd
import numpy as np

###############################################################################
# 1. DATA LOADING
###############################################################################

def load_from_excel(path, sheet_name=0):
    """
    Expects at least: Date, Close, Volume.
    Optional: Close_pair, IV
    """
    df = pd.read_excel(path, sheet_name=sheet_name)
    df = df.sort_values('Date')
    df.set_index('Date', inplace=True)
    return df

###############################################################################
# 2. FEATURE ENGINEERING
###############################################################################

def rolling_entropy(series, window=20, bins=20):
    """
    Simple Shannon entropy on rolling window using histogram bins.
    """
    def entropy_for_window(x):
        hist, _ = np.histogram(x, bins=bins, density=True)
        hist = hist[hist > 0]
        if len(hist) == 0:
            return np.nan
        return -np.sum(hist * np.log(hist))
    return series.rolling(window).apply(entropy_for_window, raw=True)


def rolling_slope(series, window=20):
    """
    Rolling slope (gradient) using simple OLS on x=0..window-1.
    """
    x = np.arange(window)
    def slope(y):
        if len(y) < window or np.all(np.isnan(y)):
            return np.nan
        return np.cov(x, y)[0, 1] / np.var(x)
    return series.rolling(window).apply(slope, raw=True)


def compute_core_features(df, price_col='Close', volume_col='Volume', window=20):
    df = df.copy()

    # Returns
    df['ret'] = df[price_col].pct_change()

    # Price gradient (trend)
    df['price_gradient'] = rolling_slope(df[price_col], window=window)

    # Realized volatility (annualized)
    df['hv'] = df['ret'].rolling(window).std() * np.sqrt(252)

    # Volatility speed (change in HV)
    df['vol_speed'] = df['hv'].diff()

    # Volume acceleration (vs rolling mean)
    df['vol_ma'] = df[volume_col].rolling(window).mean()
    df['volume_accel'] = df[volume_col] - df['vol_ma']

    # Entropy of returns
    df['entropy'] = rolling_entropy(df['ret'], window=window, bins=20)

    return df


def compute_spread_features(df, price_col='Close', pair_col='Close_pair', window=60):
    """
    Pair spread and z-score.
    If Close_pair not present, this will skip spread features gracefully.
    """
    df = df.copy()
    if pair_col not in df.columns:
        df['pair_spread'] = np.nan
        df['pair_spread_z'] = np.nan
        return df

    # Hedge ratio: for simplicity, use rolling ratio of prices (can replace with regression)
    df['hedge_ratio'] = df[price_col].rolling(window).corr(df[pair_col]) * \
                        (df[price_col].rolling(window).std() / df[pair_col].rolling(window).std())

    # If hedge_ratio becomes NaN, fallback to 1
    df['hedge_ratio'] = df['hedge_ratio'].replace([np.inf, -np.inf], np.nan).fillna(1.0)

    # Pair spread
    df['pair_spread'] = df[price_col] - df['hedge_ratio'] * df[pair_col]

    # Spread z-score
    spread_mean = df['pair_spread'].rolling(window).mean()
    spread_std = df['pair_spread'].rolling(window).std()
    df['pair_spread_z'] = (df['pair_spread'] - spread_mean) / spread_std

    return df


def compute_iv_hv_ratio(df):
    """
    IV / HV ratio.
    If IV not present, create NaN column.
    """
    df = df.copy()
    if 'IV' not in df.columns:
        df['iv_hv_ratio'] = np.nan
        return df

    df['iv_hv_ratio'] = df['IV'] / df['hv']
    return df

###############################################################################
# 3. DECISION TREE PARAMETERS & WEIGHT SCORING
###############################################################################

class DecisionTreeParams:
    def __init__(self,
                 entropy_low=None,
                 entropy_high=None,
                 grad_up_thresh=0.0,
                 grad_down_thresh=0.0,
                 vol_speed_up=None,
                 vol_speed_down=None,
                 volume_accel_min=None,
                 pair_spread_z_extreme=1.5,
                 iv_hv_high=1.2,
                 iv_hv_low=0.8):
        self.entropy_low = entropy_low
        self.entropy_high = entropy_high
        self.grad_up_thresh = grad_up_thresh
        self.grad_down_thresh = grad_down_thresh
        self.vol_speed_up = vol_speed_up
        self.vol_speed_down = vol_speed_down
        self.volume_accel_min = volume_accel_min
        self.pair_spread_z_extreme = pair_spread_z_extreme
        self.iv_hv_high = iv_hv_high
        self.iv_hv_low = iv_hv_low


def compute_weight_score(row, params: DecisionTreeParams):
    """
    Weighted scoring:
    + Trend (gradient)
    + Volume accel
    + Vol speed
    + Entropy
    + Spread z-score
    + IV/HV ratio
    """
    score = 0.0

    # Trend score
    grad = row['price_gradient']
    if not np.isnan(grad):
        if grad > params.grad_up_thresh:
            score += 0.25 * 1
        elif grad < params.grad_down_thresh:
            score += 0.25 * -1

    # Volume score
    vol_acc = row['volume_accel']
    if not np.isnan(vol_acc):
        if vol_acc > params.volume_accel_min:
            score += 0.20 * 1
        else:
            score += 0.20 * 0  # weak volume = no effect

    # Volatility speed score
    vs = row['vol_speed']
    if not np.isnan(vs):
        if vs > params.vol_speed_up:
            score += 0.20 * 1
        elif vs < params.vol_speed_down:
            score += 0.20 * -1

    # Entropy score (lower entropy = more predictable)
    ent = row['entropy']
    if not np.isnan(ent) and params.entropy_low is not None and params.entropy_high is not None:
        if ent < params.entropy_low:
            score += 0.15 * 1
        elif ent > params.entropy_high:
            score += 0.15 * -1

    # Spread z-score (mean reversion)
    spz = row.get('pair_spread_z', np.nan)
    if not np.isnan(spz):
        if abs(spz) > params.pair_spread_z_extreme:
            # We reward mean-reversion opportunities; sign is opposite of spread sign
            score += 0.10 * (-np.sign(spz))

    # IV/HV ratio
    ivhv = row.get('iv_hv_ratio', np.nan)
    if not np.isnan(ivhv):
        if ivhv < params.iv_hv_low:
            # vol cheap -> good for directional options
            score += 0.10 * 1
        elif ivhv > params.iv_hv_high:
            # vol expensive -> caution for buying options
            score += 0.10 * -1

    return score

###############################################################################
# 4. DECISION TREE LOGIC
###############################################################################

def regime_filter(row, params: DecisionTreeParams):
    """
    Layer 1: Regime.
    Returns: 'NO_TRADE', 'INCOME_ONLY', or 'TRADABLE'
    """
    entropy = row['entropy']
    vol_speed = row['vol_speed']
    volume_accel = row['volume_accel']

    if pd.isna(entropy) or pd.isna(vol_speed) or pd.isna(volume_accel):
        return 'NO_TRADE'

    if entropy > params.entropy_high:
        return 'NO_TRADE'

    if (entropy < params.entropy_low and
        abs(vol_speed) < abs(params.vol_speed_up) and
        abs(volume_accel) < abs(params.volume_accel_min)):
        return 'INCOME_ONLY'

    return 'TRADABLE'


def directional_decision(row, params: DecisionTreeParams, weight_score):
    """
    Layer 2: Direction (on tradable regime).
    Combine gradient logic + weight_score.
    Returns: 'BULL', 'BEAR', or 'NEUTRAL'
    """
    grad = row['price_gradient']
    volume_accel = row['volume_accel']

    if pd.isna(grad) or pd.isna(volume_accel):
        return 'NEUTRAL'

    has_volume = volume_accel > params.volume_accel_min

    # Base direction from gradient
    base_dir = 'NEUTRAL'
    if grad > params.grad_up_thresh and has_volume:
        base_dir = 'BULL'
    elif grad < params.grad_down_thresh and has_volume:
        base_dir = 'BEAR'

    # Adjust with weight_score
    # Score > 0.5: bullish; < -0.5: bearish
    if weight_score > 0.5:
        return 'BULL'
    elif weight_score < -0.5:
        return 'BEAR'
    else:
        return base_dir


def structure_decision(row, regime, direction, params: DecisionTreeParams):
    """
    Layer 3: Structure / strategy choice.
    Returns text label of strategy bucket.
    """
    if regime == 'NO_TRADE':
        return 'HEDGE_ONLY'

    vol_speed = row['vol_speed']
    ivhv = row.get('iv_hv_ratio', np.nan)

    if regime == 'INCOME_ONLY':
        # Neutral, income-focused
        return 'IRON_CONDOR'

    # TRADABLE regime
    if direction == 'BULL':
        if not np.isnan(ivhv) and ivhv < params.iv_hv_low:
            return 'BULL_CALL_DEBIT_SPREAD'
        if vol_speed > params.vol_speed_up:
            return 'BULL_CALL_SPREAD'
        elif vol_speed < params.vol_speed_down:
            return 'BULL_PUT_CREDIT_SPREAD'
        else:
            return 'STOCK_PLUS_COVERED_CALL'

    elif direction == 'BEAR':
        if not np.isnan(ivhv) and ivhv < params.iv_hv_low:
            return 'BEAR_PUT_DEBIT_SPREAD'
        if vol_speed > params.vol_speed_up:
            return 'BEAR_PUT_SPREAD'
        elif vol_speed < params.vol_speed_down:
            return 'BEAR_CALL_CREDIT_SPREAD'
        else:
            return 'SHORT_STOCK_PLUS_PUT_SPREAD'

    else:  # NEUTRAL
        if abs(vol_speed) < 1e-8:
            return 'BUTTERFLY'
        else:
            return 'CALENDAR_SPREAD'


def apply_decision_tree(df, params: DecisionTreeParams):
    """
    Applies full decision tree + weight scoring row-by-row.
    """
    df = df.copy()
    regimes = []
    directions = []
    strategies = []
    scores = []

    for idx, row in df.iterrows():
        weight_score = compute_weight_score(row, params)
        regime = regime_filter(row, params)
        direction = directional_decision(row, params, weight_score) if regime == 'TRADABLE' else 'NEUTRAL'
        strategy = structure_decision(row, regime, direction, params)

        scores.append(weight_score)
        regimes.append(regime)
        directions.append(direction)
        strategies.append(strategy)

    df['WeightScore'] = scores
    df['Regime'] = regimes
    df['Direction'] = directions
    df['Strategy'] = strategies

    return df

###############################################################################
# 5. SIMPLE BACKTEST LOOP
###############################################################################

def backtest_simple(df, price_col='Close'):
    """
    Very simple backtest:
    - If Strategy starts with BULL_* or STOCK_PLUS: hold +1 unit next day
    - If Strategy starts with BEAR_* or SHORT_STOCK: hold -1 unit next day
    - If NEUTRAL (e.g., BUTTERFLY, IRON_CONDOR): assume flat for now
    Returns: df with Position, StrategyRet, CumRet
    """
    df = df.copy()
    df['Position'] = 0.0

    # Determine position from strategy
    for i in range(len(df) - 1):  # position affects next day
        strategy = df['Strategy'].iloc[i]
        pos = 0.0
        if isinstance(strategy, str):
            if strategy.startswith('BULL') or strategy.startswith('STOCK_PLUS'):
                pos = 1.0
            elif strategy.startswith('BEAR') or strategy.startswith('SHORT_STOCK'):
                pos = -1.0
        df.iloc[i + 1, df.columns.get_loc('Position')] = pos

    # Strategy return: position * next-day return
    df['ret'] = df[price_col].pct_change()
    df['StrategyRet'] = df['Position'] * df['ret']
    df['CumRet'] = (1 + df['StrategyRet'].fillna(0)).cumprod() - 1

    return df

###############################################################################
# 6. MAIN EXECUTION
###############################################################################

if __name__ == '__main__':
    # === 6.1 Load data ===
    excel_path = r'C:\path\to\your\data.xlsx'   # <-- change this
    df = load_from_excel(excel_path, sheet_name=0)

    # === 6.2 Compute features ===
    df = compute_core_features(df, price_col='Close', volume_col='Volume', window=20)
    df = compute_spread_features(df, price_col='Close', pair_col='Close_pair', window=60)
    df = compute_iv_hv_ratio(df)

    # Drop initial NaN-heavy rows to clean up
    df = df.dropna(subset=['ret'])

    # === 6.3 Define parameters from quantiles ===
    # Use quantiles to automatically adapt thresholds to your data
    entropy_low = df['entropy'].quantile(0.2)
    entropy_high = df['entropy'].quantile(0.8)
    vol_speed_up = df['vol_speed'].quantile(0.7)
    vol_speed_down = df['vol_speed'].quantile(0.3)
    volume_accel_min = df['volume_accel'].quantile(0.6)

    params = DecisionTreeParams(
        entropy_low=entropy_low,
        entropy_high=entropy_high,
        grad_up_thresh=0.0,
        grad_down_thresh=0.0,
        vol_speed_up=vol_speed_up,
        vol_speed_down=vol_speed_down,
        volume_accel_min=volume_accel_min,
        pair_spread_z_extreme=1.5,
        iv_hv_high=1.2,
        iv_hv_low=0.8
    )

    # === 6.4 Apply decision tree + scoring ===
    df_signals = apply_decision_tree(df, params)

    # === 6.5 Run backtest ===
    df_bt = backtest_simple(df_signals, price_col='Close')

    # === 6.6 Inspect results ===
    print("Last 10 rows with signals and returns:")
    print(df_bt[['Close', 'entropy', 'price_gradient',
                 'hv', 'vol_speed', 'volume_accel',
                 'pair_spread', 'pair_spread_z', 'iv_hv_ratio',
                 'WeightScore', 'Regime', 'Direction', 'Strategy',
                 'Position', 'StrategyRet', 'CumRet']].tail(10))

    final_cumret = df_bt['CumRet'].iloc[-1]
    print(f"\nFinal cumulative return of simple strategy: {final_cumret:.2%}")

    # Optionally save to Excel
    out_path = r'C:\path\to\output_with_signals_and_backtest.xlsx'  # <-- change this
    df_bt.to_excel(out_path)
    print(f"\nSaved full output to: {out_path}")
