import glob
import re
import time
import hashlib
import numpy as np
import pandas as pd

NOTICE_DIR = "notices"
LABEL_FILE = "labelled_pairs.csv"

print("=" * 70)
print("Q2(c) - FAST LSH CANDIDATE GENERATION")
print("=" * 70)

# ------------------------------------------------------------
# Load
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
    return set(
        w for w in re.findall(r"[a-z]+", text)
        if len(w) >= 3
    )


print("\nCreating token sets...")

token_sets = [
    tokenize(t, b)
    for t, b in zip(
        notices["title"].fillna(""),
        notices["body"].fillna("")
    )
]


# ------------------------------------------------------------
# Token hashing
# ------------------------------------------------------------

all_tokens = set()

for s in token_sets:
    all_tokens.update(s)

print("Unique tokens  :", len(all_tokens))

token_hash = {}

for token in all_tokens:
    digest = hashlib.blake2b(
        token.encode(),
        digest_size=8
    ).digest()

    token_hash[token] = int.from_bytes(
        digest,
        "little"
    )


# ------------------------------------------------------------
# 256 MinHash
# ------------------------------------------------------------

K = 256
PRIME = 4294967311

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
            [token_hash[x] % PRIME for x in tokens],
            dtype=np.int64
        )

        hashes = (
            A[:, None] * values[None, :]
            + B[:, None]
        ) % PRIME

        signatures[row] = hashes.min(axis=1)

    return signatures


print("\nCreating 256-component signatures...")

start = time.perf_counter()

signatures = create_signatures()

print(
    "Signature time:",
    round(time.perf_counter() - start, 3),
    "seconds"
)


# ------------------------------------------------------------
# Labelled pair lookup
# ------------------------------------------------------------

id_to_index = dict(
    zip(
        notices["notice_id"],
        notices.index
    )
)

label_pairs = {}

for a, b, label in zip(
    labels["notice_id_a"],
    labels["notice_id_b"],
    labels["label"]
):

    pair = tuple(
        sorted(
            (id_to_index[a], id_to_index[b])
        )
    )

    label_pairs[pair] = str(label).lower()


same_pairs = {
    p for p, label in label_pairs.items()
    if label == "same"
}

different_pairs = {
    p for p, label in label_pairs.items()
    if label == "different"
}

print("Labelled SAME      :", len(same_pairs))
print("Labelled DIFFERENT :", len(different_pairs))


# ------------------------------------------------------------
# FAST LSH
# ------------------------------------------------------------

settings = [
    (32, 8),
    (64, 4),
    (128, 2),
    (256, 1)
]


def generate_candidates(bands, rows):

    # Instead of creating every pair in each bucket,
    # assign each notice to a bucket and use numpy grouping.

    candidate_set = set()

    for band in range(bands):

        start = band * rows
        end = start + rows

        block = signatures[:, start:end]

        # Hash each row of the band
        keys = np.array([
            hashlib.blake2b(
                row.tobytes(),
                digest_size=8
            ).digest()
            for row in block
        ])

        # Group identical keys
        order = np.argsort(keys)

        sorted_keys = keys[order]

        boundaries = np.where(
            sorted_keys[1:] != sorted_keys[:-1]
        )[0] + 1

        groups = np.split(
            order,
            boundaries
        )

        for group in groups:

            # Ignore singleton buckets
            if len(group) < 2:
                continue

            # Avoid pathological huge buckets
            if len(group) > 300:
                continue

            # Small bucket: generate pairs
            for i in range(len(group)):

                for j in range(i + 1, len(group)):

                    a = int(group[i])
                    b = int(group[j])

                    if a > b:
                        a, b = b, a

                    candidate_set.add((a, b))

    return candidate_set


# ------------------------------------------------------------
# Evaluate
# ------------------------------------------------------------

results = []

ALL_PAIRS = 12000 * 11999 // 2

for bands, rows in settings:

    print("\n" + "-" * 70)
    print(
        f"LSH setting: {bands} bands x {rows} rows"
    )
    print("-" * 70)

    start = time.perf_counter()

    candidates = generate_candidates(
        bands,
        rows
    )

    runtime = time.perf_counter() - start

    candidate_count = len(candidates)

    retrieved_same = len(
        candidates & same_pairs
    )

    retrieved_different = len(
        candidates & different_pairs
    )

    recall = (
        retrieved_same / len(same_pairs)
    )

    candidate_pct = (
        candidate_count / ALL_PAIRS
    ) * 100

    reduction = 100 - candidate_pct

    precision = (
        retrieved_same /
        (retrieved_same + retrieved_different)
        * 100
        if retrieved_same + retrieved_different
        else 0
    )

    print("Candidates              :", candidate_count)
    print(
        "Candidate % of 72M     :",
        round(candidate_pct, 6),
        "%"
    )
    print(
        "Pair reduction         :",
        round(reduction, 4),
        "%"
    )
    print(
        "Genuine SAME retrieved :",
        retrieved_same,
        "/",
        len(same_pairs)
    )
    print(
        "Recall                 :",
        round(recall * 100, 2),
        "%"
    )
    print(
        "Different candidates   :",
        retrieved_different
    )
    print(
        "Labelled precision     :",
        round(precision, 2),
        "%"
    )
    print(
        "Runtime                :",
        round(runtime, 3),
        "seconds"
    )

    results.append({
        "bands": bands,
        "rows": rows,
        "candidates": candidate_count,
        "candidate_pct": round(candidate_pct, 6),
        "pair_reduction_pct": round(reduction, 4),
        "same_retrieved": retrieved_same,
        "same_total": len(same_pairs),
        "recall_pct": round(recall * 100, 2),
        "different_retrieved": retrieved_different,
        "precision_pct": round(precision, 2),
        "runtime_seconds": round(runtime, 3)
    })


# ------------------------------------------------------------
# Save
# ------------------------------------------------------------

comparison = pd.DataFrame(results)

print("\n" + "=" * 70)
print("Q2(c) LSH TRADE-OFF")
print("=" * 70)

print(
    comparison.to_string(index=False)
)

comparison.to_csv(
    "Q2_c_lsh_comparison.csv",
    index=False
)

print("\nSaved:")
print("Q2_c_lsh_comparison.csv")

print("\nQ2(c) COMPLETED")