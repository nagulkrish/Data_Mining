import glob
import re
import time
import hashlib
import numpy as np
import pandas as pd

NOTICE_DIR = "notices"
LABEL_FILE = "labelled_pairs.csv"

print("=" * 70)
print("Q2(b) - REDUCED REPRESENTATION / MINHASH")
print("=" * 70)

# ------------------------------------------------------------
# Load data
# ------------------------------------------------------------

files = sorted(glob.glob(NOTICE_DIR + "/*.csv"))

notices = pd.concat(
    [pd.read_csv(f) for f in files],
    ignore_index=True
)

labels = pd.read_csv(LABEL_FILE)

print("Notice files   :", len(files))
print("Total notices  :", len(notices))
print("Labelled pairs :", len(labels))


# ------------------------------------------------------------
# Tokenize
# ------------------------------------------------------------

def tokenize(title, body):
    text = str(title) + " " + str(body)
    text = text.lower()
    words = re.findall(r"[a-z]+", text)
    return set(w for w in words if len(w) >= 3)


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


# ------------------------------------------------------------
# Notice lookup
# ------------------------------------------------------------

id_to_index = dict(
    zip(notices["notice_id"], notices.index)
)

ia = [
    id_to_index[x]
    for x in labels["notice_id_a"]
]

ib = [
    id_to_index[x]
    for x in labels["notice_id_b"]
]


# ------------------------------------------------------------
# Exact Jaccard for labelled pairs
# ------------------------------------------------------------

def jaccard(a, b):
    union = len(a | b)

    if union == 0:
        return 0.0

    return len(a & b) / union


print("\nCalculating exact Jaccard...")

start = time.perf_counter()

exact_scores = np.array([
    jaccard(token_sets[a], token_sets[b])
    for a, b in zip(ia, ib)
])

print(
    "Exact calculation:",
    round(time.perf_counter() - start, 3),
    "seconds"
)


# ------------------------------------------------------------
# FAST MINHASH
# ------------------------------------------------------------

# Create a fixed hash value for every unique token.
# Then derive signature positions from that value.

all_tokens = set()

for s in token_sets:
    all_tokens.update(s)

print("\nUnique tokens:", len(all_tokens))

token_list = list(all_tokens)

token_hash = {}

for token in token_list:

    digest = hashlib.blake2b(
        token.encode("utf-8"),
        digest_size=8
    ).digest()

    token_hash[token] = int.from_bytes(
        digest,
        byteorder="little"
    )


# ------------------------------------------------------------
# Generate MinHash signatures
# ------------------------------------------------------------

def create_signatures(k):

    # Deterministic random coefficients
    rng = np.random.default_rng(12345)

    prime = 4294967311

    a = rng.integers(
        1,
        prime - 1,
        size=k,
        dtype=np.int64
    )

    b = rng.integers(
        0,
        prime - 1,
        size=k,
        dtype=np.int64
    )

    signatures = np.full(
        (len(token_sets), k),
        prime,
        dtype=np.int64
    )

    # Process every notice.
    # Each token contributes to all k hash functions,
    # but the operations are vectorized.

    for row, tokens in enumerate(token_sets):

        if not tokens:
            continue

        values = np.array(
            [token_hash[x] % prime for x in tokens],
            dtype=np.int64
        )

        # Calculate k hash values for all tokens at once
        hashes = (
            (a[:, None] * values[None, :] + b[:, None])
            % prime
        )

        signatures[row] = hashes.min(axis=1)

    return signatures


# ------------------------------------------------------------
# Evaluate signature sizes
# ------------------------------------------------------------

signature_sizes = [32, 64, 128, 256]

results = []

for k in signature_sizes:

    print("\n" + "-" * 70)
    print("Signature size:", k)
    print("-" * 70)

    start = time.perf_counter()

    signatures = create_signatures(k)

    build_time = time.perf_counter() - start

    estimated_scores = np.array([
        np.mean(
            signatures[a] == signatures[b]
        )
        for a, b in zip(ia, ib)
    ])

    errors = np.abs(
        estimated_scores - exact_scores
    )

    mae = np.mean(errors)
    rmse = np.sqrt(np.mean(errors ** 2))
    max_error = np.max(errors)

    within_005 = np.mean(errors <= 0.05)
    within_010 = np.mean(errors <= 0.10)

    print(
        "Build time (sec) :",
        round(build_time, 3)
    )

    print(
        "Storage (bytes)  :",
        signatures.nbytes
    )

    print(
        "MAE              :",
        round(mae, 6)
    )

    print(
        "RMSE             :",
        round(rmse, 6)
    )

    print(
        "Maximum error    :",
        round(max_error, 6)
    )

    print(
        "Within +/-0.05   :",
        round(within_005 * 100, 2),
        "%"
    )

    print(
        "Within +/-0.10   :",
        round(within_010 * 100, 2),
        "%"
    )

    results.append({
        "signature_size": k,
        "build_seconds": round(build_time, 3),
        "storage_bytes": int(signatures.nbytes),
        "mae": round(mae, 6),
        "rmse": round(rmse, 6),
        "max_error": round(max_error, 6),
        "within_005_pct": round(within_005 * 100, 2),
        "within_010_pct": round(within_010 * 100, 2)
    })


# ------------------------------------------------------------
# Final result
# ------------------------------------------------------------

comparison = pd.DataFrame(results)

print("\n" + "=" * 70)
print("MINHASH COMPARISON")
print("=" * 70)

print(
    comparison.to_string(index=False)
)

comparison.to_csv(
    "Q2_b_minhash_comparison.csv",
    index=False
)

print("\nSaved:")
print("Q2_b_minhash_comparison.csv")

print("\nQ2(b) COMPLETED")