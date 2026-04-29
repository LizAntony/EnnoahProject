from flask import Flask, jsonify
from flask_cors import CORS
import pyodbc
import pandas as pd

app = Flask(__name__)
CORS(app)  # 👈 This line enables cross-origin requests

@app.route('/get-products')
def get_products():
    # Path to your Access database file
    db_file = r"C:\Liz\Clark\All_Documents\MBASecondSemester\SchoolSubjects\LizProjectRequirement\Project\Ennoah.accdb"

    conn_str = (
        r"Driver={Microsoft Access Driver (*.mdb, *.accdb)};"
        rf"DBQ={db_file};"
    )

    # Connect to Access
    conn = pyodbc.connect(conn_str)

    # Query products table
    #query = "SELECT * FROM ProductPrice"
    query = "SELECT [Product Name], Price, Category FROM Products ORDER BY Price;"

    df = pd.read_sql(query, conn)

    print(df.head())  # Debugging: print first rows
    conn.close()

    # Convert to JSON
    products = df.to_dict(orient="records")
    return jsonify(products)


if __name__ == '__main__':
    app.run(debug=True)