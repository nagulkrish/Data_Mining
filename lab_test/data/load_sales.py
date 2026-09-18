import os
import re
import csv
import psycopg2
from datetime import datetime, date

# --------------------------------------------------
# Configuration
# --------------------------------------------------

SALES_DIR = os.path.join(os.path.dirname(__file__), "sales")

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "database": "annapurna",
    "user": "annapurna",
    "password": "annapurna",
}

# Filename:
# SALES_S01_20240101.csv
# SALES_S01_20240101__R1.csv
FILENAME_PATTERN = re.compile(
    r"^SALES_(S\d+)_(\d{8})(?:__(R\d+))?\.(csv|parquet)$",
    re.IGNORECASE
)


# --------------------------------------------------
# Convert different source formats into one schema
# --------------------------------------------------

def parse_csv_file(filepath, store_id, business_date, filename):

    rows = []

    with open(filepath, "r", encoding="utf-8-sig", newline="") as f:

        # Read first line to determine delimiter
        first_line = f.readline()
        f.seek(0)

        delimiter = ";" if ";" in first_line else ","

        reader = csv.DictReader(
            f,
            delimiter=delimiter
        )

        for record in reader:

            # S01-S05 format
            if "product_code" in record:
                bill_no = record["bill_no"]
                line_no = record["line_no"]
                product_code = record["product_code"]
                qty = record["qty"]
                unit_price = record["unit_price"]
                line_type = record["line_type"]
                ts = record["ts"]

            # S06-S09 format
            elif "item_code" in record:
                bill_no = record["bill_no"]
                line_no = record["line_no"]
                product_code = record["item_code"]
                qty = record["quantity"]
                unit_price = record["rate"]
                line_type = record["type"]
                ts = record["txn_time"]

            # S10-S12 format
            else:
                bill_no = record["bill_no"]
                line_no = record["line_no"]
                product_code = record["product_code"]
                qty = record["qty"]
                unit_price = record["unit_price"]
                line_type = record["line_type"]
                ts = record["ts"]

            # Parse timestamp
            if store_id in ["S06", "S07", "S08", "S09"]:
                txn_ts = datetime.strptime(
                    ts,
                    "%d-%m-%Y %H:%M:%S"
                )
            elif store_id in ["S10", "S11", "S12"]:
                txn_ts = datetime.fromtimestamp(
                    int(float(ts))
                )
            else:
                txn_ts = datetime.fromisoformat(ts)

            rows.append(
                (
                    bill_no,
                    int(line_no),
                    store_id,
                    business_date,
                    product_code,
                    float(qty),
                    float(unit_price),
                    line_type.upper(),
                    txn_ts,
                    filename
                )
            )

    return rows


# --------------------------------------------------
# Connect to PostgreSQL
# --------------------------------------------------

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

total_files = 0
total_rows = 0
inserted_rows = 0
duplicate_rows = 0
skipped_files = 0

print("Starting sales load...")
print()


# --------------------------------------------------
# Process files
# --------------------------------------------------

for filename in sorted(os.listdir(SALES_DIR)):

    match = FILENAME_PATTERN.match(filename)

    if not match:
        skipped_files += 1
        continue

    store_id = match.group(1)
    date_string = match.group(2)

    business_date = datetime.strptime(
        date_string,
        "%Y%m%d"
    ).date()

    filepath = os.path.join(
        SALES_DIR,
        filename
    )

    # Currently this loader handles CSV.
    # The exam folder contains no Parquet files based
    # on our inspection.
    if not filename.lower().endswith(".csv"):
        continue

    total_files += 1

    print(
        f"Loading {total_files}: "
        f"{filename}"
    )

    rows = parse_csv_file(
        filepath,
        store_id,
        business_date,
        filename
    )

    total_rows += len(rows)

    # --------------------------------------------------
    # Idempotent insert
    # --------------------------------------------------

    for row in rows:

        cur.execute(
            """
            INSERT INTO sales_raw (
                bill_no,
                line_no,
                store_id,
                business_date,
                product_code,
                qty,
                unit_price,
                line_type,
                txn_ts,
                source_file
            )
            VALUES (
                %s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s
            )
            ON CONFLICT (bill_no, line_no)
            DO NOTHING
            """,
            row
        )

        if cur.rowcount == 1:
            inserted_rows += 1
        else:
            duplicate_rows += 1

    # Commit after each file
    conn.commit()


# --------------------------------------------------
# Finish
# --------------------------------------------------

cur.close()
conn.close()

print()
print("=" * 50)
print("SALES LOAD COMPLETE")
print("=" * 50)
print(f"Files processed   : {total_files}")
print(f"Rows read         : {total_rows}")
print(f"Rows inserted     : {inserted_rows}")
print(f"Duplicate rows    : {duplicate_rows}")
print(f"Skipped files     : {skipped_files}")
print("=" * 50)