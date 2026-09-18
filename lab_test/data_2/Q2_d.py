import glob
import re
import time
import hashlib
import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values


NOTICE_DIR = "notices"

DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "annapurna"
DB_USER = "annapurna"
DB_PASSWORD = "annapurna"

K = 256
PRIME = 4294967311

# Q2(c) operating point
BANDS = 128
ROWS = 2


print("=" * 70)
print("Q2(d) - DATABASE LSH RETRIEVAL")
print("=" * 70)


# ============================================================
# 1. LOAD NOTICES
# ============================================================

files = sorted(
    glob.glob(NOTICE_DIR + "/*.csv")
)

notices = pd.concat(
    [pd.read_csv(f) for f in files],
    ignore_index=True
)

print("Notice files :", len(files))
print("Notices      :", len(notices))


# ============================================================
# 2. TOKENIZE
# ============================================================

def tokenize(title, body):

    text = str(title) + " " + str(body)
    text = text.lower()

    return set(
        w for w in re.findall(r"[a-z]+", text)
        if len(w) >= 3
    )


print("\nCreating token sets...")

start = time.perf_counter()

token_sets = [
    tokenize(t, b)
    for t, b in zip(
        notices["title"].fillna(""),
        notices["body"].fillna("")
    )
]

print(
    "Tokenization time:",
    round(time.perf_counter() - start, 3),
    "seconds"
)


# ============================================================
# 3. HASH TOKENS
# ============================================================

all_tokens = set()

for s in token_sets:
    all_tokens.update(s)

print("Unique tokens:", len(all_tokens))

token_hash = {}

for token in all_tokens:

    digest = hashlib.blake2b(
        token.encode("utf-8"),
        digest_size=8
    ).digest()

    token_hash[token] = int.from_bytes(
        digest,
        byteorder="little"
    )


# ============================================================
# 4. CREATE 256-MINHASH SIGNATURES
# ============================================================

rng = np.random.default_rng(12345)

A = rng.integers(
    1,
    PRIME - 1,
    size=K,
    dtype=np.int64
)

B = rng.integers(
    0,
    PRIME - 1,
    size=K,
    dtype=np.int64
)


def create_signatures():

    signatures = np.full(
        (len(token_sets), K),
        PRIME,
        dtype=np.int64
    )

    for row, tokens in enumerate(token_sets):

        if not tokens:
            continue

        values = np.array(
            [
                token_hash[x] % PRIME
                for x in tokens
            ],
            dtype=np.int64
        )

        hashes = (
            A[:, None] * values[None, :]
            + B[:, None]
        ) % PRIME

        signatures[row] = hashes.min(axis=1)

    return signatures


print("\nCreating MinHash signatures...")

start = time.perf_counter()

signatures = create_signatures()

print(
    "Signature time:",
    round(time.perf_counter() - start, 3),
    "seconds"
)


# ============================================================
# 5. CONNECT TO POSTGRESQL
# ============================================================

print("\nConnecting to PostgreSQL...")

conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

cur = conn.cursor()

print("Connected.")


# ============================================================
# 6. CLEAR OLD DATA
# ============================================================

cur.execute(
    "TRUNCATE TABLE notice_lsh_bands"
)

conn.commit()

print("Old LSH rows cleared.")


# ============================================================
# 7. CREATE LSH BAND ROWS
# ============================================================

print("\nCreating LSH band rows...")

start = time.perf_counter()

rows_to_insert = []

for idx, notice_id in enumerate(
    notices["notice_id"]
):

    signature = signatures[idx]

    for band in range(BANDS):

        s = band * ROWS
        e = s + ROWS

        band_values = signature[s:e]

        band_key = hashlib.blake2b(
            band_values.tobytes(),
            digest_size=8
        ).hexdigest()

        rows_to_insert.append(
            (
                str(notice_id),
                band,
                band_key
            )
        )

print(
    "Rows prepared:",
    len(rows_to_insert)
)

print(
    "Preparation time:",
    round(time.perf_counter() - start, 3),
    "seconds"
)


# ============================================================
# 8. INSERT INTO POSTGRESQL
# ============================================================

print("\nInserting LSH bands into PostgreSQL...")

start = time.perf_counter()

insert_sql = """
INSERT INTO notice_lsh_bands
    (notice_id, band_no, band_key)
VALUES %s
"""

execute_values(
    cur,
    insert_sql,
    rows_to_insert,
    page_size=10000
)

conn.commit()

insert_time = time.perf_counter() - start

print(
    "Rows inserted:",
    len(rows_to_insert)
)

print(
    "Insert time:",
    round(insert_time, 3),
    "seconds"
)


# ============================================================
# 9. VERIFY ROW COUNT
# ============================================================

cur.execute(
    "SELECT COUNT(*) FROM notice_lsh_bands"
)

row_count = cur.fetchone()[0]

expected_rows = len(notices) * BANDS

print("\nDatabase LSH rows:", row_count)
print("Expected rows    :", expected_rows)


# ============================================================
# 10. INDEXED RETRIEVAL
# ============================================================

print("\n" + "-" * 70)
print("INDEXED RETRIEVAL")
print("-" * 70)

query_notice = str(
    notices.iloc[0]["notice_id"]
)

query_signature = signatures[0]

band_keys = []

for band in range(BANDS):

    s = band * ROWS
    e = s + ROWS

    band_key = hashlib.blake2b(
        query_signature[s:e].tobytes(),
        digest_size=8
    ).hexdigest()

    band_keys.append(
        (band, band_key)
    )


# Build VALUES clause safely
values_sql = ",".join(
    cur.mogrify(
        "(%s,%s)",
        x
    ).decode("utf-8")
    for x in band_keys
)


indexed_query = f"""
EXPLAIN (ANALYZE, BUFFERS)
SELECT DISTINCT n.notice_id
FROM notice_lsh_bands n
JOIN (
    VALUES {values_sql}
) AS q(band_no, band_key)
ON n.band_no = q.band_no
AND n.band_key = q.band_key
WHERE n.notice_id <> %s;
"""

print("\nRunning indexed query...")

cur.execute(
    indexed_query,
    (query_notice,)
)

indexed_plan = "\n".join(
    row[0]
    for row in cur.fetchall()
)

print(indexed_plan)


# ============================================================
# 11. REJECTED ALTERNATIVE - SEQUENTIAL SCAN
# ============================================================

print("\n" + "-" * 70)
print("REJECTED ALTERNATIVE - SEQUENTIAL SCAN")
print("-" * 70)

rejected_query = f"""
EXPLAIN (ANALYZE, BUFFERS)
SELECT DISTINCT n.notice_id
FROM notice_lsh_bands n
JOIN (
    VALUES {values_sql}
) AS q(band_no, band_key)
ON n.band_no = q.band_no
AND n.band_key = q.band_key
WHERE n.notice_id <> %s;
"""

print("\nRunning sequential-scan comparison...")

cur.execute(
    "SET enable_indexscan = off"
)

cur.execute(
    rejected_query,
    (query_notice,)
)

rejected_plan = "\n".join(
    row[0]
    for row in cur.fetchall()
)

print(rejected_plan)

cur.execute(
    "RESET enable_indexscan"
)


# ============================================================
# 12. SAVE EXPLAIN PLANS
# ============================================================

with open(
    "Q2_d_indexed_plan.txt",
    "w",
    encoding="utf-8"
) as f:

    f.write(indexed_plan)


with open(
    "Q2_d_sequential_plan.txt",
    "w",
    encoding="utf-8"
) as f:

    f.write(rejected_plan)


# ============================================================
# 13. CLOSE
# ============================================================

cur.close()
conn.close()


print("\n" + "=" * 70)
print("Q2(d) DATABASE BUILD COMPLETED")
print("=" * 70)

print("Database rows :", row_count)
print("Expected rows :", expected_rows)

print("\nSaved:")
print("Q2_d_indexed_plan.txt")
print("Q2_d_sequential_plan.txt")