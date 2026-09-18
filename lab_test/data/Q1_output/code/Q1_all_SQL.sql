-- ============================================================
-- Q1 COMPLETE SQL / COMMAND RECORD
-- Annapurna Stores Data Engineering / Analytics Lab
-- Organized by Q1(a) through Q1(f)
-- ============================================================

-- ============================================================
-- Q1(a) : PostgreSQL MASTER DATA CHECKS
-- ============================================================

\dt

SELECT * FROM stores LIMIT 10;
SELECT * FROM products LIMIT 10;
SELECT * FROM product_categories LIMIT 10;
SELECT * FROM price_revisions LIMIT 10;

SELECT COUNT(*) AS store_count FROM stores;
SELECT COUNT(*) AS product_count FROM products;
SELECT COUNT(*) AS category_count FROM product_categories;
SELECT COUNT(*) AS price_revision_count FROM price_revisions;

-- Sales table created for raw ingestion
CREATE TABLE IF NOT EXISTS sales_raw (
    bill_no TEXT NOT NULL,
    line_no INTEGER NOT NULL,
    store_id TEXT NOT NULL,
    business_date DATE NOT NULL,
    product_code TEXT NOT NULL,
    qty NUMERIC,
    unit_price NUMERIC(12,2),
    line_type TEXT NOT NULL,
    txn_ts TIMESTAMP,
    source_file TEXT NOT NULL,
    PRIMARY KEY (bill_no, line_no)
);

-- ============================================================
-- Q1(a) : OBJECT-STORE / PARTITION VERIFICATION
-- ============================================================
-- MinIO object organization used:
-- sales/store=Sxx/month=YYYY-MM/<filename>

-- These are shell commands, retained here for the exam record:
-- mc ls --recursive local/annapurna-raw/sales | wc -l
-- mc ls --recursive local/annapurna-raw/sales/store=S01/month=2024-01 | wc -l
-- dir SALES_S01_202401*.csv

-- Expected evidence:
-- Total sales files: 4457
-- S01 January 2024 files: 31
-- S01 January 2024 bytes: 580704


-- ============================================================
-- Q1(b) : IDEMPOTENT LOAD VERIFICATION
-- ============================================================

SELECT COUNT(*) AS row_count
FROM sales_raw;

SELECT
    line_type,
    COUNT(*) AS row_count
FROM sales_raw
GROUP BY line_type
ORDER BY line_type;

SELECT
    COUNT(*) AS total_rows,
    COUNT(DISTINCT (bill_no, line_no)) AS distinct_bill_lines
FROM sales_raw;

-- Final deterministic row-count + checksum
SELECT COUNT(*) AS row_count,
       md5(string_agg(
           concat_ws('|',
               bill_no,
               line_no,
               store_id,
               business_date,
               product_code,
               qty,
               unit_price,
               line_type,
               txn_ts
           ),
           E'\n' ORDER BY bill_no,line_no
       )) AS checksum
FROM sales_raw;

-- Loader runs recorded:
-- Run 1:
-- Files processed: 4457
-- Rows read: 1137585
-- Rows inserted: 1120924
-- Duplicate rows: 16661
-- Skipped: 0
--
-- Run 2:
-- Files processed: 4457
-- Rows read: 1137585
-- Rows inserted: 0
-- Duplicate rows: 1137585
-- Skipped: 0
--
-- Run 3:
-- Files processed: 4457
-- Rows read: 1137585
-- Rows inserted: 0
-- Duplicate rows: 1137585
-- Skipped: 0
--
-- Final row count: 1120924
-- Final checksum:
-- 77c760db667185700452d0915b73e69b


-- ============================================================
-- Q1(c) : STAR-SCHEMA / DASHBOARD TABLES
-- ============================================================

DROP TABLE IF EXISTS dim_store;
CREATE TABLE dim_store AS
SELECT
    store_id,
    store_name,
    address_line,
    city,
    state,
    region,
    floor_area_sqft,
    opened_on
FROM stores;

DROP TABLE IF EXISTS dim_product;
CREATE TABLE dim_product AS
SELECT
    product_sk,
    product_code,
    product_name,
    category_id,
    brand,
    pack_size,
    uom,
    valid_from,
    valid_to,
    is_current
FROM products;

DROP TABLE IF EXISTS dim_category;
CREATE TABLE dim_category AS
SELECT
    category_id,
    category_name,
    department,
    gst_rate
FROM product_categories;

-- Fact table:
-- SALE and RETURN and DISCOUNT are revenue lines.
-- TAX and TENDER are excluded.
-- A bill containing VOID is removed as a complete bill.
-- Product identity is resolved using product code + business date.
-- Historical price is obtained from price_revisions.

DROP TABLE IF EXISTS fact_sales;

CREATE TABLE fact_sales AS
WITH void_bills AS (
    SELECT DISTINCT bill_no
    FROM sales_raw
    WHERE line_type = 'VOID'
)
SELECT
    s.bill_no,
    s.line_no,
    s.store_id,
    s.business_date,
    s.product_code,
    s.qty,
    s.line_type,
    p.product_sk,
    p.category_id,
    CASE
        WHEN s.line_type = 'SALE'
            THEN s.qty * pr.selling_price
        WHEN s.line_type IN ('RETURN', 'DISCOUNT')
            THEN s.qty * pr.selling_price
        ELSE 0
    END AS net_amount,
    EXTRACT(DOW FROM s.business_date) AS day_of_week
FROM sales_raw s
JOIN products p
    ON p.product_code = s.product_code
   AND s.business_date >= p.valid_from
   AND (p.valid_to IS NULL OR s.business_date < p.valid_to)
LEFT JOIN price_revisions pr
    ON pr.product_sk = p.product_sk
   AND s.business_date >= pr.effective_from
   AND (pr.effective_to IS NULL OR s.business_date < pr.effective_to)
WHERE s.line_type IN ('SALE', 'RETURN', 'DISCOUNT')
  AND s.bill_no NOT IN (SELECT bill_no FROM void_bills);

-- Dimension/fact counts
SELECT COUNT(*) AS dim_store_count FROM dim_store;
SELECT COUNT(*) AS dim_product_count FROM dim_product;
SELECT COUNT(*) AS dim_category_count FROM dim_category;
SELECT COUNT(*) AS fact_sales_count FROM fact_sales;

-- Expected:
-- dim_store = 12
-- dim_product = 1224
-- dim_category = 14
-- fact_sales = 757205

-- Check fact table structure
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'fact_sales'
ORDER BY ordinal_position;

-- Dashboard by store / category / day-of-week / month
SELECT
    ds.store_name,
    dc.category_name,
    f.day_of_week,
    TO_CHAR(f.business_date, 'YYYY-MM') AS month,
    ROUND(SUM(f.net_amount), 2) AS revenue
FROM fact_sales f
JOIN dim_store ds
    ON f.store_id = ds.store_id
JOIN dim_category dc
    ON f.category_id = dc.category_id
GROUP BY
    ds.store_name,
    dc.category_name,
    f.day_of_week,
    TO_CHAR(f.business_date, 'YYYY-MM')
ORDER BY month, ds.store_name, dc.category_name, f.day_of_week;


-- ============================================================
-- Q1(d) : HISTORICAL PRICE REVISIONS / AS-OF REPORTING
-- ============================================================

-- Inspect March-effective price revisions
SELECT
    p.product_code,
    p.product_name,
    pr.selling_price,
    pr.effective_from,
    pr.effective_to
FROM products p
JOIN price_revisions pr
    ON p.product_sk = pr.product_sk
WHERE pr.effective_from <= DATE '2024-03-31'
  AND (pr.effective_to IS NULL OR pr.effective_to >= DATE '2024-03-01')
ORDER BY p.product_code
LIMIT 10;

-- March 2024 historical-price revenue
SELECT
    TO_CHAR(business_date, 'YYYY-MM') AS month,
    ROUND(SUM(net_amount), 2) AS revenue
FROM fact_sales
WHERE business_date >= DATE '2024-03-01'
  AND business_date < DATE '2024-04-01'
GROUP BY 1;

-- April 2024 historical-price revenue
-- Same query, only reporting period changed.
SELECT
    TO_CHAR(business_date, 'YYYY-MM') AS month,
    ROUND(SUM(net_amount), 2) AS revenue
FROM fact_sales
WHERE business_date >= DATE '2024-04-01'
  AND business_date < DATE '2024-05-01'
GROUP BY 1;

-- Expected:
-- March = 42209951.560
-- April = 38154091.520


-- ============================================================
-- Q1(e) : DUCKDB FEDERATED QUERY
-- ============================================================

-- DuckDB setup:
-- INSTALL httpfs;
-- LOAD httpfs;
-- INSTALL postgres;
-- LOAD postgres;

-- PostgreSQL federation:
-- ATTACH 'dbname=annapurna host=127.0.0.1 port=5432
-- user=annapurna password=annapurna'
-- AS pg (TYPE postgres);

-- MinIO S3 secret:
-- CREATE SECRET minio_secret (
--     TYPE S3,
--     KEY_ID 'admin',
--     SECRET 'admin12345',
--     REGION 'us-east-1',
--     ENDPOINT '127.0.0.1:9000',
--     USE_SSL false,
--     URL_STYLE 'path'
-- );

-- Confirm attached databases:
-- SHOW DATABASES;

-- Direct object-store read:
-- SELECT *
-- FROM read_csv_auto(
--   's3://annapurna-raw/sales/store=S01/month=2024-01/*.csv'
-- )
-- LIMIT 5;

-- Federated query: MinIO CSV + PostgreSQL stores
SELECT
    p.state,
    SUM(
        CAST(s.qty AS DOUBLE) *
        CAST(s.unit_price AS DOUBLE)
    ) AS total_amount
FROM read_csv_auto(
    's3://annapurna-raw/sales/store=S01/month=2024-01/*.csv'
) s
JOIN pg.public.stores p
    ON s.store = p.store_id
WHERE s.line_type = 'SALE'
GROUP BY p.state;

-- Expected result:
-- Karnataka | 4532434.520000006

-- Query plan evidence:
-- EXPLAIN
-- SELECT
--     p.state,
--     SUM(CAST(s.qty AS DOUBLE) * CAST(s.unit_price AS DOUBLE))
-- FROM read_csv_auto(
--     's3://annapurna-raw/sales/store=S01/month=2024-01/*.csv'
-- ) s
-- JOIN pg.public.stores p
--   ON s.store = p.store_id
-- WHERE s.line_type = 'SALE'
-- GROUP BY p.state;

-- Expected plan operators include:
-- POSTGRES_SCAN
-- READ_CSV_AUTO
-- HASH_JOIN
-- HASH_GROUP_BY


-- ============================================================
-- Q1(f) : FINANCE RECONCILIATION
-- ============================================================

-- Revenue by line type
SELECT
    line_type,
    COUNT(*) AS row_count,
    ROUND(SUM(qty * unit_price), 2) AS amount
FROM sales_raw
GROUP BY line_type
ORDER BY line_type;

-- Known line-type interpretation:
-- SALE       = revenue
-- RETURN     = subtracts
-- DISCOUNT   = subtracts
-- VOID       = cancels
-- TAX        = not revenue
-- TENDER     = not revenue; bill total / includes GST

-- Printed-price vs historical-price diagnostic
SELECT
    TO_CHAR(s.business_date, 'YYYY-MM') AS month,
    ROUND(SUM(
        CASE
            WHEN s.line_type IN ('SALE','RETURN','DISCOUNT')
            THEN s.qty * s.unit_price
            ELSE 0
        END
    ), 2) AS printed_price_revenue,
    ROUND(SUM(COALESCE(f.net_amount, 0)), 2) AS historical_price_revenue
FROM sales_raw s
LEFT JOIN fact_sales f
    ON s.bill_no = f.bill_no
   AND s.line_no = f.line_no
GROUP BY 1
ORDER BY 1;

-- Finance-definition source revenue:
-- SALE/RETURN/DISCOUNT only, excluding complete VOID bills.
SELECT
    TO_CHAR(business_date, 'YYYY-MM') AS month,
    ROUND(SUM(
        CASE
            WHEN line_type IN ('SALE','RETURN','DISCOUNT')
            THEN qty * unit_price
            ELSE 0
        END
    ), 2) AS source_revenue
FROM sales_raw s
WHERE NOT EXISTS (
    SELECT 1
    FROM sales_raw v
    WHERE v.bill_no = s.bill_no
      AND v.line_type = 'VOID'
)
GROUP BY 1
ORDER BY 1;

-- Expected source-revenue result:
-- 2024-01 | 38446071.33
-- 2024-02 | 34887085.55
-- 2024-03 | 41971649.09
-- 2024-04 | 37958457.37
-- 2024-05 | 41764716.40
-- 2024-06 | 38987082.82
-- 2024-07 | 40295160.11
-- 2024-08 | 45252181.75
-- 2024-09 | 44615037.46
-- 2024-10 | 56359195.92
-- 2024-11 | 51583838.47
-- 2024-12 | 50745259.48

-- July S07 gap check
SELECT
    business_date,
    COUNT(*) AS row_count
FROM sales_raw
WHERE store_id = 'S07'
  AND business_date >= DATE '2024-07-01'
  AND business_date < DATE '2024-08-01'
GROUP BY business_date
ORDER BY business_date;

-- This check shows the documented missing S07 dates:
-- 2024-07-09
-- 2024-07-10
-- 2024-07-11

-- ============================================================
-- END OF Q1 SQL RECORD
-- ============================================================
