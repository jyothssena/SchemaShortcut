import duckdb
import glob
import os

def get_schema_summary(data_dir="data/DBSnapshot/"):
    conn = duckdb.connect()
    summary = []
    
    parquet_files = glob.glob(os.path.join(data_dir, "*.parquet"))
    if not parquet_files:
        return "No schema data found."

    for f in parquet_files:
        table_name = os.path.basename(f).replace(".parquet", "")
        try:
            # Query the schema of the parquet file
            res = conn.execute(f"DESCRIBE SELECT * FROM '{f}'").fetchall()
            columns = [f"{row[0]} ({row[1]})" for row in res]
            summary.append(f"Table: {table_name}\nColumns: {', '.join(columns)}")
        except Exception as e:
            # Skip problematic files like the empty ones we found earlier
            continue
            
    return "\n\n".join(summary)

if __name__ == "__main__":
    print(get_schema_summary())
