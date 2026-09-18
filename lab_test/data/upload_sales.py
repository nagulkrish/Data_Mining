import os
import re
import boto3
from botocore.client import Config

# -----------------------------
# MinIO connection
# -----------------------------
MINIO_ENDPOINT = "http://127.0.0.1:9000"
MINIO_ACCESS_KEY = "admin"
MINIO_SECRET_KEY = "admin12345"
BUCKET = "annapurna-raw"

SALES_DIR = os.path.join(os.path.dirname(__file__), "sales")

# Create MinIO/S3 client
s3 = boto3.client(
    "s3",
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
    config=Config(signature_version="s3v4"),
    region_name="us-east-1"
)

# -----------------------------
# Upload files
# -----------------------------
pattern = re.compile(
    r"^SALES_(S\d+)_(\d{8})(?:__(R\d+))?\.(csv|parquet)$",
    re.IGNORECASE
)

uploaded = 0
skipped = 0

for filename in sorted(os.listdir(SALES_DIR)):

    match = pattern.match(filename)

    if not match:
        skipped += 1
        print(f"SKIP: {filename}")
        continue

    store_id = match.group(1)
    business_date = match.group(2)

    year = business_date[:4]
    month = business_date[4:6]

    # Partition layout:
    # sales/store=S01/month=2024-01/file.csv
    object_key = (
        f"sales/"
        f"store={store_id}/"
        f"month={year}-{month}/"
        f"{filename}"
    )

    local_file = os.path.join(SALES_DIR, filename)

    print(f"Uploading: {filename}")
    print(f"       -> {object_key}")

    s3.upload_file(
        local_file,
        BUCKET,
        object_key
    )

    uploaded += 1

print()
print("================================")
print("UPLOAD COMPLETE")
print("================================")
print(f"Uploaded files : {uploaded}")
print(f"Skipped files  : {skipped}")