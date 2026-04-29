from flask import Flask, jsonify
from flask_cors import CORS
import pandas as pd

import psycopg2

app = Flask(__name__)

CORS(app)  # 👈 This line enables cross-origin requests

@app.route('/get-products')
def get_products():

conn = psycopg2.connect(
        host="localhost",
        database="Liz",
        user="eantony@clarku.edu",
        password="Imissyou@123"
    )

    # Query product data
    query = "SELECT * FROM products"
    df = pd.read_sql(query, conn)

    # Close connection
    conn.close()

    # Convert to JSON
    products = df.to_dict(orient='records')

    return jsonify(products)

if __name__ == '__main__':
    app.run(debug=True)