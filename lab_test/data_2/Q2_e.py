import glob
import time
import pandas as pd


print("=" * 70)
print("Q2(e) - FULL CORPUS PORTAL SKEW ANALYSIS")
print("=" * 70)


# ------------------------------------------------------------
# 1. LOAD ALL 12,000 NOTICES
# ------------------------------------------------------------

files = sorted(
    glob.glob("notices/*.csv")
)

start = time.perf_counter()

df = pd.concat(
    [pd.read_csv(f) for f in files],
    ignore_index=True
)

load_time = time.perf_counter() - start

print("Notice files :", len(files))
print("Total notices:", len(df))
print("Load time    :", round(load_time, 3), "seconds")


# ------------------------------------------------------------
# 2. BASIC PORTAL DISTRIBUTION
# ------------------------------------------------------------

portal_counts = (
    df.groupby("portal_id")
      .size()
      .sort_values(ascending=False)
)

print("\n" + "-" * 70)
print("TOP 15 PORTALS BY NOTICE COUNT")
print("-" * 70)

print(
    portal_counts.head(15).to_string()
)


# ------------------------------------------------------------
# 3. SHARE OF CORPUS
# ------------------------------------------------------------

top1 = portal_counts.head(1).sum()
top5 = portal_counts.head(5).sum()
top7 = portal_counts.head(7).sum()
top15 = portal_counts.head(15).sum()

total = len(df)

print("\n" + "-" * 70)
print("PORTAL CONCENTRATION")
print("-" * 70)

print(
    "Top 1 notices :",
    top1,
    f"({top1 / total * 100:.2f}%)"
)

print(
    "Top 5 notices :",
    top5,
    f"({top5 / total * 100:.2f}%)"
)

print(
    "Top 7 notices :",
    top7,
    f"({top7 / total * 100:.2f}%)"
)

print(
    "Top 15 notices:",
    top15,
    f"({top15 / total * 100:.2f}%)"
)


# ------------------------------------------------------------
# 4. TEXT SIZE BY PORTAL
# ------------------------------------------------------------

df["text_length"] = (
    df["title"].fillna("").astype(str).str.len()
    +
    df["body"].fillna("").astype(str).str.len()
)

portal_stats = (
    df.groupby("portal_id")
      .agg(
          notices=("notice_id", "count"),
          total_chars=("text_length", "sum"),
          avg_chars=("text_length", "mean"),
          median_chars=("text_length", "median")
      )
      .sort_values(
          "total_chars",
          ascending=False
      )
)

print("\n" + "-" * 70)
print("TOP 15 PORTALS BY TOTAL TEXT VOLUME")
print("-" * 70)

print(
    portal_stats.head(15).to_string()
)


# ------------------------------------------------------------
# 5. CORPUS TEXT CONCENTRATION
# ------------------------------------------------------------

total_chars = df["text_length"].sum()

print("\n" + "-" * 70)
print("TEXT-VOLUME CONCENTRATION")
print("-" * 70)

for n in [1, 5, 7, 15]:

    chars = portal_stats.head(n)["total_chars"].sum()

    print(
        f"Top {n:2d} portals text:",
        chars,
        f"({chars / total_chars * 100:.2f}%)"
    )


# ------------------------------------------------------------
# 6. COST PROXY
# ------------------------------------------------------------

# A simple mechanically measurable CPU-work proxy:
# total characters processed.

df["token_count"] = (
    df["body"]
    .fillna("")
    .astype(str)
    .str.findall(r"[A-Za-z]+")
    .str.len()
)

portal_cost = (
    df.groupby("portal_id")
      .agg(
          notices=("notice_id", "count"),
          characters=("text_length", "sum"),
          tokens=("token_count", "sum")
      )
      .sort_values(
          "tokens",
          ascending=False
      )
)

total_tokens = portal_cost["tokens"].sum()

print("\n" + "-" * 70)
print("TOP PORTALS BY TOKEN WORK")
print("-" * 70)

display_cost = portal_cost.head(15).copy()

display_cost["token_share_pct"] = (
    display_cost["tokens"]
    / total_tokens
    * 100
)

print(
    display_cost.to_string()
)


# ------------------------------------------------------------
# 7. SAVE RESULTS
# ------------------------------------------------------------

portal_counts.rename(
    "notice_count"
).to_csv(
    "Q2_e_portal_counts.csv"
)

portal_stats.to_csv(
    "Q2_e_portal_text_stats.csv"
)

portal_cost.to_csv(
    "Q2_e_portal_cost_proxy.csv"
)


print("\n" + "=" * 70)
print("Q2(e) STEP 1 COMPLETED")
print("=" * 70)

print("Saved:")
print("Q2_e_portal_counts.csv")
print("Q2_e_portal_text_stats.csv")
print("Q2_e_portal_cost_proxy.csv")