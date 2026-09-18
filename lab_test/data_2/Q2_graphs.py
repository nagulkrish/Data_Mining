import os
import pandas as pd
import matplotlib.pyplot as plt

BASE = os.path.dirname(os.path.abspath(__file__))

print("=" * 70)
print("Q2 GRAPH GENERATION")
print("=" * 70)

# ============================================================
# Q2(c) - REQUIRED GRAPH
# True-similarity probability against candidate-stage settings
# ============================================================

c_file = os.path.join(BASE, "Q2_c_lsh_comparison.csv")

if not os.path.exists(c_file):
    print("ERROR: Q2_c_lsh_comparison.csv not found!")
    exit()

c = pd.read_csv(c_file)

print("\nQ2(c) data:")
print(c.to_string(index=False))

# Create LSH setting from actual CSV columns
c["setting"] = (
    c["bands"].astype(str)
    + "×"
    + c["rows"].astype(str)
)

# ------------------------------------------------------------
# Graph 1: True similarity retrieval vs LSH setting
# ------------------------------------------------------------

plt.figure(figsize=(9, 5))

plt.plot(
    c["setting"],
    c["recall_pct"],
    marker="o",
    linewidth=2
)

plt.xlabel("LSH bands × rows")
plt.ylabel("True-similarity retrieval (%)")
plt.title(
    "Q2(c) - True-Similarity Retrieval vs Candidate-Stage Setting"
)

plt.ylim(0, 100)
plt.grid(True, alpha=0.3)

# Add values above points
for x, y in zip(c["setting"], c["recall_pct"]):
    plt.text(
        x,
        y + 2,
        f"{y:.2f}%",
        ha="center"
    )

plt.tight_layout()

c_out = os.path.join(
    BASE,
    "Q2_c_required_graph.png"
)

plt.savefig(
    c_out,
    dpi=200
)

plt.show()

print("\nSaved:", c_out)


# ============================================================
# Q2(e) - PORTAL SKEW GRAPH
# ============================================================

portal_file = os.path.join(
    BASE,
    "Q2_e_portal_counts.csv"
)

if not os.path.exists(portal_file):
    print("ERROR: Q2_e_portal_counts.csv not found!")
    exit()

p = pd.read_csv(portal_file)

print("\nQ2(e) portal data:")
print(p.head(15).to_string(index=False))

# Find portal column
portal_col = None

for col in p.columns:
    if col.lower() in [
        "portal_id",
        "portal",
        "portalid"
    ]:
        portal_col = col
        break

# Find notice-count column
count_col = None

for col in p.columns:
    if (
        "count" in col.lower()
        or "notice" in col.lower()
    ):
        count_col = col
        break

if portal_col is None or count_col is None:
    print("ERROR: Could not identify portal/count columns.")
    print("Columns found:", list(p.columns))
    exit()

top = p.sort_values(
    count_col,
    ascending=False
).head(15)

# ------------------------------------------------------------
# Graph 2: Portal concentration
# ------------------------------------------------------------

plt.figure(figsize=(10, 6))

plt.bar(
    top[portal_col].astype(str),
    top[count_col]
)

plt.xlabel("Portal")
plt.ylabel("Number of notices")
plt.title(
    "Q2(e) - Notice Concentration Across Top Portals"
)

plt.xticks(rotation=45)

plt.tight_layout()

portal_out = os.path.join(
    BASE,
    "Q2_e_portal_skew_graph.png"
)

plt.savefig(
    portal_out,
    dpi=200
)

plt.show()

print("Saved:", portal_out)


# ============================================================
# Q2(e) - BEFORE / AFTER RUNTIME
# ============================================================

ba_file = os.path.join(
    BASE,
    "Q2_e_before_after.csv"
)

if not os.path.exists(ba_file):
    print("ERROR: Q2_e_before_after.csv not found!")
    exit()

ba = pd.read_csv(ba_file).iloc[0]

baseline_runtime = float(
    ba["baseline_runtime_sec"]
)

mitigated_runtime = float(
    ba["mitigated_runtime_sec"]
)

# ------------------------------------------------------------
# Graph 3: Runtime comparison
# ------------------------------------------------------------

plt.figure(figsize=(7, 5))

plt.bar(
    ["Baseline", "Mitigated"],
    [
        baseline_runtime,
        mitigated_runtime
    ]
)

plt.ylabel("Runtime (seconds)")
plt.title(
    "Q2(e) - Baseline vs Mitigated Runtime"
)

plt.tight_layout()

runtime_out = os.path.join(
    BASE,
    "Q2_e_runtime_graph.png"
)

plt.savefig(
    runtime_out,
    dpi=200
)

plt.show()

print("Saved:", runtime_out)


# ============================================================
# Q2(e) - RETRIEVAL QUALITY
# ============================================================

baseline_recall = (
    float(ba["baseline_recall"]) * 100
)

mitigated_recall = (
    float(ba["mitigated_recall"]) * 100
)

baseline_precision = (
    float(ba["baseline_precision"]) * 100
)

mitigated_precision = (
    float(ba["mitigated_precision"]) * 100
)

x = [0, 1]
width = 0.35

# ------------------------------------------------------------
# Graph 4: Recall and precision comparison
# ------------------------------------------------------------

plt.figure(figsize=(8, 5))

plt.bar(
    [i - width / 2 for i in x],
    [
        baseline_recall,
        baseline_precision
    ],
    width,
    label="Baseline"
)

plt.bar(
    [i + width / 2 for i in x],
    [
        mitigated_recall,
        mitigated_precision
    ],
    width,
    label="Mitigated"
)

plt.xticks(
    x,
    [
        "Recall",
        "Precision"
    ]
)

plt.ylabel("Percentage (%)")

plt.title(
    "Q2(e) - Retrieval Quality Before vs After Mitigation"
)

plt.ylim(0, 100)

plt.legend()

plt.tight_layout()

quality_out = os.path.join(
    BASE,
    "Q2_e_quality_graph.png"
)

plt.savefig(
    quality_out,
    dpi=200
)

plt.show()

print("Saved:", quality_out)


# ============================================================
# FINAL OUTPUT
# ============================================================

print("\n")
print("=" * 70)
print("ALL Q2 GRAPHS GENERATED SUCCESSFULLY")
print("=" * 70)

print()
print("1. Q2_c_required_graph.png")
print("2. Q2_e_portal_skew_graph.png")
print("3. Q2_e_runtime_graph.png")
print("4. Q2_e_quality_graph.png")

print()
print("Q2(c) REQUIRED GRAPH      : COMPLETED")
print("Q2(e) PORTAL SKEW GRAPH   : COMPLETED")
print("Q2(e) RUNTIME GRAPH       : COMPLETED")
print("Q2(e) QUALITY GRAPH       : COMPLETED")

print()
print("COMPLETED - FILE THE GRAPH SCREENSHOTS")
print("=" * 70)