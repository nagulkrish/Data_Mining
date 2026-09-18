import os
import re
import time
import hashlib
import numpy as np
import pandas as pd
from collections import Counter, defaultdict

# ============================================================
# Q2(e) - PORTAL-AWARE BOILERPLATE MITIGATION
# ============================================================

BASE = os.path.dirname(os.path.abspath(__file__))
NOTICES_DIR = os.path.join(BASE, "notices")
LABEL_FILE = os.path.join(BASE, "labelled_pairs.csv")

K = 256
PRIME = 4294967311
BANDS = 128
ROWS = 2

# Portal groups explicitly described in portal_profiles.md
NATIONAL_PORTALS = {"P001", "P002", "P005"}
STATE_PORTALS = {"P003", "P004", "P006"}
BOILERPLATE_PORTALS = NATIONAL_PORTALS | STATE_PORTALS

TOKEN_RE = re.compile(r"[a-z]+")


def tokenize(text):
    return set(TOKEN_RE.findall(str(text).lower()))


def load_data():
    frames = []

    for fn in sorted(os.listdir(NOTICES_DIR)):
        if fn.lower().endswith(".csv"):
            path = os.path.join(NOTICES_DIR, fn)
            frames.append(pd.read_csv(path))

    df = pd.concat(frames, ignore_index=True)

    labels = pd.read_csv(LABEL_FILE)

    return df, labels


def build_original_tokens(df):
    return [
        tokenize(str(row.title) + " " + str(row.body))
        for row in df.itertuples(index=False)
    ]


def build_portal_specific_common_tokens(df, original_tokens):
    """
    Find tokens that occur in >=80% of notices within the
    portal groups known to contain repeated boilerplate.
    """

    portal_docs = defaultdict(list)

    for i, portal in enumerate(df["portal_id"].astype(str)):
        if portal in BOILERPLATE_PORTALS:
            portal_docs[portal].append(i)

    common_tokens = {}

    for portal, indices in portal_docs.items():

        counts = Counter()

        for i in indices:
            for token in original_tokens[i]:
                counts[token] += 1

        threshold = max(2, int(np.ceil(len(indices) * 0.80)))

        common = {
            token
            for token, count in counts.items()
            if count >= threshold
        }

        common_tokens[portal] = common

        print(
            f"{portal}: {len(indices):4d} notices | "
            f"{len(common):4d} high-frequency boilerplate tokens"
        )

    return common_tokens


def apply_mitigation(df, original_tokens, common_tokens):
    mitigated = []

    removed_counts = []

    for i, tokens in enumerate(original_tokens):

        portal = str(df.iloc[i]["portal_id"])

        if portal in common_tokens:
            remove = common_tokens[portal]
            new_tokens = tokens - remove
        else:
            new_tokens = tokens.copy()

        mitigated.append(new_tokens)
        removed_counts.append(len(tokens) - len(new_tokens))

    return mitigated, removed_counts


def make_vocab(token_sets):
    vocab = {}
    for tokens in token_sets:
        for token in tokens:
            if token not in vocab:
                vocab[token] = len(vocab) + 1

    return vocab


def make_signatures(token_sets, vocab):
    rng = np.random.default_rng(12345)

    a = rng.integers(1, PRIME, size=K, dtype=np.int64)
    b = rng.integers(0, PRIME, size=K, dtype=np.int64)

    signatures = np.full(
        (len(token_sets), K),
        PRIME,
        dtype=np.int64
    )

    for i, tokens in enumerate(token_sets):

        if not tokens:
            continue

        ids = np.array(
            [vocab[t] for t in tokens],
            dtype=np.int64
        )

        # K x number_of_tokens
        hv = (
            a[:, None] * ids[None, :] +
            b[:, None]
        ) % PRIME

        signatures[i] = hv.min(axis=1)

    return signatures


def make_lsh(signatures):
    buckets = defaultdict(list)

    for i in range(len(signatures)):

        for band in range(BANDS):

            start = band * ROWS
            end = start + ROWS

            values = signatures[i, start:end]

            key = hashlib.blake2b(
                values.tobytes(),
                digest_size=8
            ).hexdigest()

            buckets[(band, key)].append(i)

    return buckets


def evaluate_pairs(df, labels, buckets):
    id_to_index = {
        str(row.notice_id): i
        for i, row in enumerate(df.itertuples(index=False))
    }

    same_retrieved = 0
    different_retrieved = 0
    total_same = 0

    for row in labels.itertuples(index=False):

        a = str(row.notice_id_a)
        b = str(row.notice_id_b)
        label = str(row.label).lower()

        if a not in id_to_index or b not in id_to_index:
            continue

        ia = id_to_index[a]
        ib = id_to_index[b]

        retrieved = False

        for band in range(BANDS):

            start = band * ROWS
            end = start + ROWS

            # We need the signatures here, handled by caller.
            pass

    return same_retrieved, different_retrieved


def evaluate_with_signatures(df, labels, signatures, buckets):

    id_to_index = {
        str(row.notice_id): i
        for i, row in enumerate(df.itertuples(index=False))
    }

    same_total = 0
    same_retrieved = 0

    different_total = 0
    different_retrieved = 0

    for row in labels.itertuples(index=False):

        a = str(row.notice_id_a)
        b = str(row.notice_id_b)
        label = str(row.label).lower()

        if a not in id_to_index or b not in id_to_index:
            continue

        ia = id_to_index[a]
        ib = id_to_index[b]

        retrieved = False

        for band in range(BANDS):

            start = band * ROWS
            end = start + ROWS

            key_a = hashlib.blake2b(
                signatures[ia, start:end].tobytes(),
                digest_size=8
            ).hexdigest()

            key_b = hashlib.blake2b(
                signatures[ib, start:end].tobytes(),
                digest_size=8
            ).hexdigest()

            if key_a == key_b:
                retrieved = True
                break

        if label == "same":
            same_total += 1
            if retrieved:
                same_retrieved += 1

        elif label == "different":
            different_total += 1
            if retrieved:
                different_retrieved += 1

    recall = (
        same_retrieved / same_total
        if same_total else 0
    )

    candidate_precision = (
        same_retrieved /
        (same_retrieved + different_retrieved)
        if (same_retrieved + different_retrieved) else 0
    )

    return {
        "same_total": same_total,
        "same_retrieved": same_retrieved,
        "different_total": different_total,
        "different_retrieved": different_retrieved,
        "recall": recall,
        "precision": candidate_precision
    }


def count_candidate_pairs(buckets):
    """
    Count unique candidate pairs generated by LSH.
    """
    pairs = set()

    for members in buckets.values():

        if len(members) < 2:
            continue

        members = sorted(set(members))

        for x in range(len(members)):
            for y in range(x + 1, len(members)):
                pairs.add((members[x], members[y]))

    return len(pairs)


# ============================================================
# MAIN
# ============================================================

print("=" * 70)
print("Q2(e) - PORTAL-AWARE MITIGATION")
print("=" * 70)

t0 = time.perf_counter()

df, labels = load_data()

print(f"Notices       : {len(df)}")
print(f"Labelled pairs: {len(labels)}")

# ------------------------------------------------------------
# Original tokenization
# ------------------------------------------------------------

t1 = time.perf_counter()

original_tokens = build_original_tokens(df)

print(
    f"Original tokenization: "
    f"{time.perf_counter() - t1:.3f} sec"
)

original_total_tokens = sum(len(x) for x in original_tokens)
original_avg_tokens = original_total_tokens / len(original_tokens)

print(f"Original total unique-token count: {original_total_tokens:,}")
print(f"Original average tokens/notice    : {original_avg_tokens:.2f}")

# ------------------------------------------------------------
# Identify portal boilerplate
# ------------------------------------------------------------

print("\nIdentifying portal-specific repeated boilerplate...")

common_tokens = build_portal_specific_common_tokens(
    df,
    original_tokens
)

# ------------------------------------------------------------
# Apply mitigation
# ------------------------------------------------------------

t2 = time.perf_counter()

mitigated_tokens, removed_counts = apply_mitigation(
    df,
    original_tokens,
    common_tokens
)

mitigation_time = time.perf_counter() - t2

mitigated_total_tokens = sum(len(x) for x in mitigated_tokens)
mitigated_avg_tokens = mitigated_total_tokens / len(mitigated_tokens)

print("\nMITIGATION EFFECT")
print("-" * 70)
print(f"Mitigation processing time : {mitigation_time:.3f} sec")
print(f"Tokens before              : {original_total_tokens:,}")
print(f"Tokens after               : {mitigated_total_tokens:,}")
print(f"Tokens removed             : {original_total_tokens - mitigated_total_tokens:,}")
print(
    f"Reduction                  : "
    f"{100 * (1 - mitigated_total_tokens / original_total_tokens):.2f}%"
)
print(f"Average tokens before      : {original_avg_tokens:.2f}")
print(f"Average tokens after       : {mitigated_avg_tokens:.2f}")

# ------------------------------------------------------------
# MinHash
# ------------------------------------------------------------

print("\nCreating mitigated MinHash signatures...")

t3 = time.perf_counter()

vocab = make_vocab(mitigated_tokens)

print(f"Mitigated vocabulary size: {len(vocab)}")

signatures = make_signatures(
    mitigated_tokens,
    vocab
)

signature_time = time.perf_counter() - t3

print(
    f"Mitigated MinHash time: "
    f"{signature_time:.3f} sec"
)

# ------------------------------------------------------------
# LSH
# ------------------------------------------------------------

print("\nBuilding mitigated LSH buckets...")

t4 = time.perf_counter()

buckets = make_lsh(signatures)

lsh_time = time.perf_counter() - t4

candidate_count = count_candidate_pairs(buckets)

print(f"LSH build time : {lsh_time:.3f} sec")
print(f"Buckets        : {len(buckets)}")
print(f"Candidate pairs: {candidate_count:,}")

# ------------------------------------------------------------
# Retrieval quality
# ------------------------------------------------------------

quality = evaluate_with_signatures(
    df,
    labels,
    signatures,
    buckets
)

print("\nRETRIEVAL QUALITY AFTER MITIGATION")
print("-" * 70)

print(
    f"SAME pairs retrieved : "
    f"{quality['same_retrieved']}/{quality['same_total']}"
)

print(
    f"SAME recall          : "
    f"{quality['recall'] * 100:.2f}%"
)

print(
    f"DIFFERENT retrieved  : "
    f"{quality['different_retrieved']}/{quality['different_total']}"
)

print(
    f"Labelled precision   : "
    f"{quality['precision'] * 100:.2f}%"
)

# ------------------------------------------------------------
# Runtime
# ------------------------------------------------------------

total_runtime = time.perf_counter() - t0

print("\n" + "=" * 70)
print("BEFORE / AFTER")
print("=" * 70)

print("BASELINE")
print("  Runtime          : 133.811 sec")
print("  Runtime          : 2.23 min")
print("  Recall           : 86.02%")
print("  Precision        : 70.59%")

print("\nMITIGATED")
print(f"  Runtime          : {total_runtime:.3f} sec")
print(f"  Runtime          : {total_runtime / 60:.2f} min")
print(f"  Recall           : {quality['recall'] * 100:.2f}%")
print(f"  Precision        : {quality['precision'] * 100:.2f}%")

runtime_change = (
    100 * (1 - total_runtime / 133.811)
)

print("\nRuntime reduction:")
print(f"  {runtime_change:.2f}%")

# ------------------------------------------------------------
# Save evidence
# ------------------------------------------------------------

result = pd.DataFrame([{
    "baseline_runtime_sec": 133.811,
    "mitigated_runtime_sec": total_runtime,
    "baseline_recall": 0.8602,
    "mitigated_recall": quality["recall"],
    "baseline_precision": 0.7059,
    "mitigated_precision": quality["precision"],
    "original_tokens": original_total_tokens,
    "mitigated_tokens": mitigated_total_tokens,
    "token_reduction_percent":
        100 * (1 - mitigated_total_tokens / original_total_tokens),
    "candidate_pairs_after": candidate_count,
    "same_retrieved_after": quality["same_retrieved"],
    "same_total": quality["same_total"],
    "different_retrieved_after": quality["different_retrieved"],
    "different_total": quality["different_total"]
}])

result.to_csv(
    os.path.join(BASE, "Q2_e_before_after.csv"),
    index=False
)

print("\nSaved: Q2_e_before_after.csv")

print("\n" + "=" * 70)
print("Q2(e) MITIGATION COMPLETED")
print("=" * 70)