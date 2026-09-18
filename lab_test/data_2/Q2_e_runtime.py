import glob
import re
import time
import hashlib
import pandas as pd


print("=" * 70)
print("Q2(e) - FULL CORPUS BASELINE RUNTIME")
print("=" * 70)


# ------------------------------------------------------------
# LOAD CORPUS
# ------------------------------------------------------------

files = sorted(glob.glob("notices/*.csv"))

start = time.perf_counter()

df = pd.concat(
    [pd.read_csv(f) for f in files],
    ignore_index=True
)

load_time = time.perf_counter() - start

print("Notice files :", len(files))
print("Notices      :", len(df))
print("Load time    :", round(load_time, 3), "seconds")


# ------------------------------------------------------------
# TEXT REPRESENTATION
# ------------------------------------------------------------

print("\nCreating token sets...")

start = time.perf_counter()

token_sets = []

for title, body in zip(
    df["title"].fillna(""),
    df["body"].fillna("")
):

    text = (str(title) + " " + str(body)).lower()

    tokens = set(
        re.findall(r"[a-z]+", text)
    )

    token_sets.append(tokens)

token_time = time.perf_counter() - start

print(
    "Tokenization time:",
    round(token_time, 3),
    "seconds"
)


# ------------------------------------------------------------
# MINHASH
# ------------------------------------------------------------

K = 256
PRIME = 4294967311

rng = __import__("numpy").random.default_rng(12345)

A = rng.integers(
    1,
    PRIME - 1,
    size=K,
    dtype="int64"
)

B = rng.integers(
    0,
    PRIME - 1,
    size=K,
    dtype="int64"
)


def hash_token(token):

    return int.from_bytes(
        hashlib.blake2b(
            token.encode("utf-8"),
            digest_size=8
        ).digest(),
        "little"
    ) % PRIME


print("\nCreating MinHash signatures...")

start = time.perf_counter()

signatures = []

for tokens in token_sets:

    if not tokens:
        signatures.append(
            [PRIME] * K
        )
        continue

    values = [
        hash_token(t)
        for t in tokens
    ]

    sig = []

    for i in range(K):

        minimum = PRIME

        a = int(A[i])
        b = int(B[i])

        for value in values:

            h = (a * value + b) % PRIME

            if h < minimum:
                minimum = h

        sig.append(minimum)

    signatures.append(sig)

signature_time = time.perf_counter() - start

print(
    "Signature time:",
    round(signature_time, 3),
    "seconds"
)


# ------------------------------------------------------------
# LSH INDEX BUILD
# ------------------------------------------------------------

BANDS = 128
ROWS = 2

print("\nBuilding LSH buckets...")

start = time.perf_counter()

buckets = {}

for notice_index, sig in enumerate(signatures):

    for band in range(BANDS):

        start_row = band * ROWS
        end_row = start_row + ROWS

        band_values = sig[start_row:end_row]

        key = hashlib.blake2b(
            str(band_values).encode("utf-8"),
            digest_size=8
        ).hexdigest()

        bucket_key = (band, key)

        if bucket_key not in buckets:
            buckets[bucket_key] = []

        buckets[bucket_key].append(
            notice_index
        )

lsh_time = time.perf_counter() - start

print(
    "LSH build time:",
    round(lsh_time, 3),
    "seconds"
)

print(
    "Number of buckets:",
    len(buckets)
)


# ------------------------------------------------------------
# BASELINE TOTAL
# ------------------------------------------------------------

total_time = (
    load_time
    + token_time
    + signature_time
    + lsh_time
)

print("\n" + "-" * 70)
print("BASELINE RUNTIME")
print("-" * 70)

print(
    "Load time      :",
    round(load_time, 3),
    "sec"
)

print(
    "Tokenization   :",
    round(token_time, 3),
    "sec"
)

print(
    "MinHash        :",
    round(signature_time, 3),
    "sec"
)

print(
    "LSH build      :",
    round(lsh_time, 3),
    "sec"
)

print(
    "TOTAL RUNTIME  :",
    round(total_time, 3),
    "sec"
)

print(
    "TOTAL MINUTES  :",
    round(total_time / 60, 2),
    "min"
)

print(
    "20-MINUTE BUDGET:",
    "PASS" if total_time <= 1200 else "FAIL"
)


print("\n" + "=" * 70)
print("Q2(e) BASELINE COMPLETED")
print("=" * 70)