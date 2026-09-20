[README.md](https://github.com/user-attachments/files/32434120/README.md)
# Data Mining Lab

This repository contains the Data Mining laboratory work, including data loading, processing, similarity analysis, retrieval, database indexing, and performance evaluation.

## Repository Structure

```text
Data_Mining/
└── lab_test/
    ├── data/
    │   ├── masters/
    │   ├── sales/
    │   └── upload_sales.py
    │
    └── data_2/
        ├── notices/
        ├── _truth/
        ├── labelled_pairs.csv
        ├── portal_profiles.md
        │
        ├── Q2_a.py
        ├── Q2_a_method_comparison.csv
        ├── Q2_b.py
        ├── Q2_b_minhash_comparison.csv
        ├── Q2_c.py
        ├── Q2_c_lsh_comparison.csv
        ├── Q2_c_required_graph.png
        ├── Q2_d.py
        ├── Q2_d_indexed_plan.txt
        ├── Q2_d_sequential_plan.txt
        ├── Q2_e.py
        ├── Q2_e_mitigated.py
        ├── Q2_e_runtime.py
        ├── Q2_graphs.py
        └── Q2_OUTPUTS/
```

## Q1 — Data Loading and Integration

Q1 contains the data loading and integration workflow using PostgreSQL and MinIO.

The workflow includes:

- Loading master data.
- Loading sales data from multiple CSV files.
- Integrating the datasets.
- Storing and querying data using PostgreSQL.
- Using MinIO for object storage.
- Validating the final loaded data.

## Q2 — Twelve Thousand Tenders, Wearing Disguises

Q2 investigates similarity between procurement/tender notices and develops an efficient retrieval pipeline for identifying potentially similar notices.

The dataset contains **12,000 notices** across multiple CSV shards and **900 labelled pairs** for evaluating similarity retrieval.

### Q2(a) — Similarity Definition and Baseline Comparison

Two TF-IDF based text representations were evaluated:

- Word TF-IDF unigrams
- Word TF-IDF 1–3 grams

The evaluation used the labelled pairs to compare similarity predictions against the `same` / `different` labels.

The 1–3 gram representation achieved:

- Accuracy: **0.9722**
- Precision: **0.9601**
- Recall: **0.9498**
- F1: **0.9550**
- ROC-AUC: **0.9936**

The detailed comparison is stored in:

```text
Q2_a_method_comparison.csv
```

### Q2(b) — Reduced Representation with MinHash

MinHash signatures were used to create a compact representation of token sets while estimating Jaccard similarity.

Four signature sizes were evaluated:

| Signature Size | MAE | RMSE | Within ±0.05 |
|---:|---:|---:|---:|
| 32 | 0.062928 | 0.078339 | 45.56% |
| 64 | 0.038947 | 0.049462 | 68.56% |
| 128 | 0.025091 | 0.032647 | 86.22% |
| 256 | 0.017695 | 0.022483 | 96.22% |

The comparison is stored in:

```text
Q2_b_minhash_comparison.csv
```

### Q2(c) — Candidate Generation with LSH

Locality-Sensitive Hashing (LSH) was used to avoid comparing every possible pair of 12,000 notices.

Four band/row configurations were evaluated:

| Bands × Rows | Same-Pair Recall | Labelled Precision | Pair Reduction |
|---|---:|---:|---:|
| 32 × 8 | 54.12% | 55.72% | 91.70% |
| 64 × 4 | 77.78% | 59.13% | 86.67% |
| 128 × 2 | **86.02%** | **70.59%** | **89.75%** |
| 256 × 1 | 84.23% | 78.86% | 94.47% |

The 128 × 2 configuration was used for the subsequent retrieval workflow.

Graph:

![Q2(c) LSH Retrieval](Q2_c_required_graph.png)

Results:

```text
Q2_c_lsh_comparison.csv
```

### Q2(d) — Database Retrieval Structure

The LSH band keys were persisted in PostgreSQL using the following logical structure:

```text
notice_lsh_bands
├── notice_id
├── band_no
└── band_key
```

Indexes were created to support band-key retrieval.

The indexed retrieval plan and the rejected bitmap-based alternative are stored as:

```text
Q2_d_indexed_plan.txt
Q2_d_sequential_plan.txt
```

Measured execution times:

- Indexed plan: **203.337 ms**
- Bitmap heap scan alternative: **259.236 ms**

The indexed approach examined 427,314 matching band rows during the retrieval operation.

### Q2(e) — Full Corpus Skew and Mitigation

The full corpus contains 12,000 notices distributed across 260 portals.

The portal distribution is highly concentrated. The top 15 portals account for approximately **63.97% of notices** and **69.35% of total text volume**.

The analysis measures:

- Notice count by portal.
- Text volume by portal.
- Token-work concentration.
- Full-corpus runtime.
- Retrieval quality.
- A portal-aware boilerplate mitigation.

Baseline full-corpus runtime:

```text
133.811 seconds
2.23 minutes
```

This was within the 20-minute budget.

The mitigation removed high-frequency boilerplate tokens from the identified portal groups. It reduced the token count by **31.13%**, but the measured MinHash/LSH workflow became slower overall:

```text
Baseline:
Runtime  : 133.811 sec
Recall   : 86.02%
Precision: 70.59%

Mitigated:
Runtime  : 322.632 sec
Recall   : 99.64%
Precision: 31.66%
```

This demonstrates the trade-off between retrieval recall, candidate selectivity, and processing cost.

Graphs and detailed measurements are available in:

```text
Q2_e_portal_counts.csv
Q2_e_portal_text_stats.csv
Q2_e_portal_cost_proxy.csv
Q2_e_before_after.csv
Q2_e_portal_skew_graph.png
Q2_e_runtime_graph.png
Q2_e_quality_graph.png
```

## Technologies Used

- Python
- Pandas
- NumPy
- PostgreSQL
- Docker
- MinIO
- TF-IDF
- MinHash
- Locality-Sensitive Hashing (LSH)
- CSV
- Matplotlib

## Running the Q2 Analysis

From the Q2 directory:

```powershell
cd lab_test\data_2
```

Run the individual analysis scripts as required:

```powershell
python Q2_a.py
python Q2_b.py
python Q2_c.py
python Q2_d.py
python Q2_e.py
python Q2_e_runtime.py
python Q2_e_mitigated.py
```

Graphs can be regenerated with:

```powershell
python Q2_graphs.py
```

## Output Files

The `Q2_OUTPUTS` directory contains the main evidence files:

- MinHash comparison results
- LSH comparison results
- PostgreSQL execution plans
- Portal skew analysis
- Runtime comparison
- Retrieval-quality comparison
- Required graphs

## Dataset

The Q2 dataset includes:

- `12,000` tender notices
- `900` labelled pairs
- `260` portals
- Notice text, portal, publication date, estimated value, and closing date fields

The labelled pairs are used to evaluate similarity retrieval quality.

## Results Summary

The experiments demonstrate a complete similarity-retrieval pipeline:

```text
Tender Notices
      ↓
Text / Token Representation
      ↓
Similarity Estimation
      ↓
MinHash Signatures
      ↓
LSH Candidate Generation
      ↓
PostgreSQL Indexed Retrieval
      ↓
Full-Corpus Performance Analysis
      ↓
Portal-Aware Mitigation
      ↓
Quality vs Cost Evaluation
```

## Author

**Nagul Krishnan**

B.Tech — Computer Science & Artificial Intelligence
