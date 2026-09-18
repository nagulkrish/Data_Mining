import re
import time
import numpy as np
import pandas as pd

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    roc_auc_score,
    confusion_matrix
)

# ==============================
# Q2(a) - Notice Similarity
# ==============================

NOTICE_DIR = "notices"
LABEL_FILE = "labelled_pairs.csv"

# ---------- Load notices ----------
files = sorted(__import__("glob").glob(NOTICE_DIR + "/*.csv"))

notices = pd.concat(
    [pd.read_csv(f) for f in files],
    ignore_index=True
)

labels = pd.read_csv(LABEL_FILE)

print("=" * 70)
print("Q2(a) - NOTICE SIMILARITY")
print("=" * 70)

print("Number of notice files :", len(files))
print("Number of notices     :", len(notices))
print("Number of labelled pairs:", len(labels))

print("\nLabel distribution:")
print(labels["label"].value_counts())

print("\nLabel percentage:")
print(
    (labels["label"].value_counts(normalize=True) * 100).round(2)
)

# ---------- Text cleaning ----------
def clean_text(title, body):
    text = str(title) + " " + str(body)
    text = text.lower()

    # Remove numbers and punctuation.
    # This removes reference numbers, dates and monetary formatting.
    text = re.sub(r"[^a-z]+", " ", text)

    return re.sub(r"\s+", " ", text).strip()


notices["text"] = [
    clean_text(title, body)
    for title, body in zip(
        notices["title"].fillna(""),
        notices["body"].fillna("")
    )
]

# ---------- Map notice IDs ----------
id_to_index = pd.Series(
    notices.index,
    index=notices["notice_id"]
).to_dict()

ia = np.array(
    [id_to_index[x] for x in labels["notice_id_a"]]
)

ib = np.array(
    [id_to_index[x] for x in labels["notice_id_b"]]
)

y = (
    labels["label"].astype(str).str.lower() == "same"
).astype(int).to_numpy()


# ---------- Evaluate one method ----------
def evaluate_method(name, ngram_range):

    print("\n" + "-" * 70)
    print(name)
    print("-" * 70)

    start = time.perf_counter()

    vectorizer = TfidfVectorizer(
        ngram_range=ngram_range,
        min_df=2,
        max_df=0.98,
        sublinear_tf=True
    )

    X = vectorizer.fit_transform(notices["text"])

    build_time = time.perf_counter() - start

    pair_start = time.perf_counter()

    scores = np.asarray(
        X[ia].multiply(X[ib]).sum(axis=1)
    ).ravel()

    pair_time = time.perf_counter() - pair_start

    # Find threshold giving maximum F1 on labelled data
    best = None

    for threshold in np.linspace(0.05, 0.95, 181):

        prediction = (
            scores >= threshold
        ).astype(int)

        precision, recall, f1, _ = (
            precision_recall_fscore_support(
                y,
                prediction,
                average="binary",
                zero_division=0
            )
        )

        if best is None or f1 > best["f1"]:

            best = {
                "threshold": threshold,
                "accuracy": accuracy_score(y, prediction),
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "auc": roc_auc_score(y, scores),
                "confusion": confusion_matrix(
                    y, prediction
                ).ravel()
            }

    print("Features             :", X.shape[1])
    print("Non-zero values     :", X.nnz)
    print("Build time (sec)    :", round(build_time, 3))
    print("Pair scoring (sec)  :", round(pair_time, 3))
    print("Best threshold      :", round(best["threshold"], 3))
    print("Accuracy            :", round(best["accuracy"], 4))
    print("Precision           :", round(best["precision"], 4))
    print("Recall              :", round(best["recall"], 4))
    print("F1                  :", round(best["f1"], 4))
    print("ROC-AUC             :", round(best["auc"], 4))

    print(
        "Confusion matrix [TN FP FN TP]:",
        best["confusion"]
    )

    return vectorizer, X, scores, best


# ---------- Compare two approaches ----------

results = []

for name, ngram in [
    ("Word TF-IDF Unigrams", (1, 1)),
    ("Word TF-IDF 1-3 grams", (1, 3))
]:

    vectorizer, X, scores, best = evaluate_method(
        name,
        ngram
    )

    results.append({
        "method": name,
        "features": X.shape[1],
        "build_seconds": round(
            time.perf_counter(), 4
        ),
        "threshold": round(
            best["threshold"], 3
        ),
        "accuracy": round(
            best["accuracy"], 4
        ),
        "precision": round(
            best["precision"], 4
        ),
        "recall": round(
            best["recall"], 4
        ),
        "f1": round(
            best["f1"], 4
        ),
        "auc": round(
            best["auc"], 4
        )
    })


print("\n" + "=" * 70)
print("METHOD COMPARISON")
print("=" * 70)

comparison = pd.DataFrame(results)

print(comparison.to_string(index=False))


# ---------- Save outputs ----------

comparison.to_csv(
    "Q2_a_method_comparison.csv",
    index=False
)

print("\nQ2(a) analysis finished.")
print("Output saved to Q2_a_method_comparison.csv")