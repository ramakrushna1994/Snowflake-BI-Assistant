-- ============================================================
-- 08_semantic_views.sql
-- Pre-aggregated semantic views to avoid re-running common
-- Last updated: 2026-07-24 (CI/CD test)
-- question patterns. Used by DataForge app for direct routing.
-- ============================================================

USE DATABASE CONVERSATIONAL_BI;
USE WAREHOUSE BI_ASSISTANT_WH;

-- ════════════════════════════════════════════════════════════
-- SALES SEMANTIC VIEWS
-- ════════════════════════════════════════════════════════════
USE SCHEMA SALES;

-- V_MONTHLY_REVENUE
-- Answers: monthly revenue trend, revenue by month/year
-- NOTE: order-grain measures (order count, AOV) are computed separately from
--       line-item measures to avoid fan-out from the ORDERS->ORDER_ITEMS join.
CREATE OR REPLACE VIEW V_MONTHLY_REVENUE AS
WITH line_items AS (
    SELECT
        DATE_TRUNC('MONTH', o.ORDER_DATE)          AS REVENUE_MONTH,
        TO_CHAR(o.ORDER_DATE, 'YYYY-MM')           AS MONTH_LABEL,
        SUM(oi.QUANTITY * oi.UNIT_PRICE)           AS GROSS_REVENUE,
        SUM(oi.DISCOUNT_PCT / 100 * oi.UNIT_PRICE * oi.QUANTITY) AS TOTAL_DISCOUNTS,
        SUM(oi.LINE_TOTAL)                         AS NET_REVENUE
    FROM ORDERS o
    JOIN ORDER_ITEMS oi ON o.ORDER_ID = oi.ORDER_ID
    WHERE o.STATUS != 'Cancelled'
    GROUP BY 1, 2
),
orders_agg AS (
    SELECT
        DATE_TRUNC('MONTH', ORDER_DATE)            AS REVENUE_MONTH,
        COUNT(DISTINCT ORDER_ID)                   AS TOTAL_ORDERS,
        COUNT(DISTINCT CUSTOMER_ID)                AS UNIQUE_CUSTOMERS,
        AVG(TOTAL_AMOUNT)                          AS AVG_ORDER_VALUE
    FROM ORDERS
    WHERE STATUS != 'Cancelled'
    GROUP BY 1
)
SELECT
    li.REVENUE_MONTH,
    li.MONTH_LABEL,
    oa.TOTAL_ORDERS,
    oa.UNIQUE_CUSTOMERS,
    li.GROSS_REVENUE,
    li.TOTAL_DISCOUNTS,
    li.NET_REVENUE,
    oa.AVG_ORDER_VALUE
FROM line_items li
JOIN orders_agg oa ON li.REVENUE_MONTH = oa.REVENUE_MONTH
ORDER BY li.REVENUE_MONTH;

-- V_PRODUCT_PERFORMANCE
-- Answers: top/bottom products, revenue by category/subcategory
-- NOTE: order-item and return metrics are pre-aggregated separately to avoid
--       join fan-out (a product with N line-items and M returns would otherwise
--       produce N*M rows and inflate every SUM).
CREATE OR REPLACE VIEW V_PRODUCT_PERFORMANCE AS
WITH oi_agg AS (
    SELECT
        PRODUCT_ID,
        COUNT(DISTINCT ORDER_ITEM_ID) AS TIMES_ORDERED,
        SUM(QUANTITY)                 AS TOTAL_UNITS_SOLD,
        SUM(QUANTITY * UNIT_PRICE)    AS GROSS_REVENUE,
        SUM(LINE_TOTAL)               AS NET_REVENUE
    FROM ORDER_ITEMS
    GROUP BY PRODUCT_ID
),
ret_agg AS (
    SELECT
        PRODUCT_ID,
        COUNT(DISTINCT RETURN_ID) AS TOTAL_RETURNS
    FROM RETURNS
    GROUP BY PRODUCT_ID
)
SELECT
    p.PRODUCT_ID,
    p.PRODUCT_NAME,
    p.CATEGORY,
    p.SUBCATEGORY,
    p.UNIT_PRICE,
    p.UNIT_COST,
    p.UNIT_PRICE - p.UNIT_COST                AS UNIT_MARGIN,
    ROUND((p.UNIT_PRICE - p.UNIT_COST) / NULLIF(p.UNIT_PRICE, 0) * 100, 2) AS MARGIN_PCT,
    COALESCE(oi.TIMES_ORDERED, 0)             AS TIMES_ORDERED,
    COALESCE(oi.TOTAL_UNITS_SOLD, 0)          AS TOTAL_UNITS_SOLD,
    COALESCE(oi.GROSS_REVENUE, 0)             AS GROSS_REVENUE,
    COALESCE(oi.NET_REVENUE, 0)               AS NET_REVENUE,
    COALESCE(r.TOTAL_RETURNS, 0)              AS TOTAL_RETURNS,
    ROUND(COALESCE(r.TOTAL_RETURNS, 0) / NULLIF(oi.TOTAL_UNITS_SOLD, 0) * 100, 2) AS RETURN_RATE_PCT
FROM PRODUCTS p
LEFT JOIN oi_agg oi ON p.PRODUCT_ID = oi.PRODUCT_ID
LEFT JOIN ret_agg r ON p.PRODUCT_ID = r.PRODUCT_ID;

-- V_CUSTOMER_SEGMENTS
-- Answers: revenue by region/segment, top customers, customer LTV
-- NOTE: order-item revenue and returns are pre-aggregated per customer to avoid
--       fan-out from the ORDERS->ORDER_ITEMS->RETURNS one-to-many joins.
CREATE OR REPLACE VIEW V_CUSTOMER_SEGMENTS AS
WITH order_rev AS (
    SELECT
        o.CUSTOMER_ID,
        COUNT(DISTINCT o.ORDER_ID)   AS TOTAL_ORDERS,
        SUM(oi.LINE_TOTAL)           AS LIFETIME_VALUE,
        MAX(o.ORDER_DATE)            AS LAST_ORDER_DATE
    FROM ORDERS o
    JOIN ORDER_ITEMS oi ON o.ORDER_ID = oi.ORDER_ID
    WHERE o.STATUS != 'Cancelled'
    GROUP BY o.CUSTOMER_ID
),
order_aov AS (
    SELECT CUSTOMER_ID, AVG(TOTAL_AMOUNT) AS AVG_ORDER_VALUE
    FROM ORDERS
    WHERE STATUS != 'Cancelled'
    GROUP BY CUSTOMER_ID
),
cust_returns AS (
    SELECT o.CUSTOMER_ID, COUNT(DISTINCT r.RETURN_ID) AS TOTAL_RETURNS
    FROM ORDERS o
    JOIN RETURNS r ON o.ORDER_ID = r.ORDER_ID
    GROUP BY o.CUSTOMER_ID
)
SELECT
    c.CUSTOMER_ID,
    c.FIRST_NAME || ' ' || c.LAST_NAME         AS CUSTOMER_NAME,
    c.REGION,
    c.STATE,
    c.SEGMENT,
    sc.CHANNEL_NAME                             AS ACQUISITION_CHANNEL,
    COALESCE(orv.TOTAL_ORDERS, 0)               AS TOTAL_ORDERS,
    COALESCE(orv.LIFETIME_VALUE, 0)             AS LIFETIME_VALUE,
    aov.AVG_ORDER_VALUE                         AS AVG_ORDER_VALUE,
    orv.LAST_ORDER_DATE                         AS LAST_ORDER_DATE,
    DATEDIFF('DAY', orv.LAST_ORDER_DATE, CURRENT_DATE()) AS DAYS_SINCE_LAST_ORDER,
    COALESCE(cr.TOTAL_RETURNS, 0)               AS TOTAL_RETURNS
FROM CUSTOMERS c
LEFT JOIN order_rev orv     ON c.CUSTOMER_ID = orv.CUSTOMER_ID
LEFT JOIN order_aov aov     ON c.CUSTOMER_ID = aov.CUSTOMER_ID
LEFT JOIN cust_returns cr   ON c.CUSTOMER_ID = cr.CUSTOMER_ID
LEFT JOIN SALES_CHANNELS sc ON c.CHANNEL_ID  = sc.CHANNEL_ID;

-- V_RETURN_ANALYSIS
-- Answers: return rates, return reasons, returns by product/category
CREATE OR REPLACE VIEW V_RETURN_ANALYSIS AS
SELECT
    p.CATEGORY,
    p.SUBCATEGORY,
    p.PRODUCT_NAME,
    r.RETURN_REASON,
    r.RETURN_STATUS,
    DATE_TRUNC('MONTH', r.RETURN_DATE)         AS RETURN_MONTH,
    COUNT(DISTINCT r.RETURN_ID)                AS RETURN_COUNT,
    SUM(r.REFUND_AMOUNT)                       AS TOTAL_REFUNDS,
    AVG(r.REFUND_AMOUNT)                       AS AVG_REFUND
FROM RETURNS r
JOIN PRODUCTS p ON r.PRODUCT_ID = p.PRODUCT_ID
GROUP BY 1, 2, 3, 4, 5, 6;

-- V_CHANNEL_PERFORMANCE
-- Answers: sales by channel, channel mix, channel revenue
-- NOTE: order-grain measures (orders, customers, AOV, discounts) are computed
--       separately from line-item revenue to avoid ORDERS->ORDER_ITEMS fan-out.
CREATE OR REPLACE VIEW V_CHANNEL_PERFORMANCE AS
WITH line_rev AS (
    SELECT
        o.CHANNEL_ID,
        DATE_TRUNC('MONTH', o.ORDER_DATE) AS ORDER_MONTH,
        SUM(oi.LINE_TOTAL)                AS NET_REVENUE
    FROM ORDERS o
    JOIN ORDER_ITEMS oi ON o.ORDER_ID = oi.ORDER_ID
    WHERE o.STATUS != 'Cancelled'
    GROUP BY 1, 2
),
order_agg AS (
    SELECT
        CHANNEL_ID,
        DATE_TRUNC('MONTH', ORDER_DATE)   AS ORDER_MONTH,
        COUNT(DISTINCT ORDER_ID)          AS TOTAL_ORDERS,
        COUNT(DISTINCT CUSTOMER_ID)       AS UNIQUE_CUSTOMERS,
        AVG(TOTAL_AMOUNT)                 AS AVG_ORDER_VALUE,
        SUM(DISCOUNT_AMOUNT)              AS TOTAL_DISCOUNTS
    FROM ORDERS
    WHERE STATUS != 'Cancelled'
    GROUP BY 1, 2
)
SELECT
    sc.CHANNEL_NAME,
    sc.CHANNEL_TYPE,
    oa.ORDER_MONTH,
    oa.TOTAL_ORDERS,
    oa.UNIQUE_CUSTOMERS,
    lr.NET_REVENUE,
    oa.AVG_ORDER_VALUE,
    oa.TOTAL_DISCOUNTS
FROM order_agg oa
JOIN line_rev lr       ON oa.CHANNEL_ID = lr.CHANNEL_ID AND oa.ORDER_MONTH = lr.ORDER_MONTH
JOIN SALES_CHANNELS sc ON oa.CHANNEL_ID = sc.CHANNEL_ID;

-- ════════════════════════════════════════════════════════════
-- HR SEMANTIC VIEWS
-- ════════════════════════════════════════════════════════════
USE SCHEMA HR;

-- V_DEPT_SUMMARY
-- Answers: headcount by dept, avg salary, budget utilisation
CREATE OR REPLACE VIEW V_DEPT_SUMMARY AS
SELECT
    d.DEPT_ID,
    d.DEPT_NAME,
    d.LOCATION,
    d.ANNUAL_BUDGET,
    d.HEADCOUNT_BUDGET,
    COUNT(CASE WHEN e.STATUS = 'Active' THEN 1 END)  AS ACTIVE_HEADCOUNT,
    COUNT(e.EMP_ID)                                  AS TOTAL_HEADCOUNT,
    AVG(CASE WHEN e.STATUS = 'Active' THEN e.SALARY END) AS AVG_SALARY,
    MIN(CASE WHEN e.STATUS = 'Active' THEN e.SALARY END) AS MIN_SALARY,
    MAX(CASE WHEN e.STATUS = 'Active' THEN e.SALARY END) AS MAX_SALARY,
    SUM(CASE WHEN e.STATUS = 'Active' THEN e.SALARY END) AS TOTAL_SALARY_COST,
    ROUND(SUM(CASE WHEN e.STATUS='Active' THEN e.SALARY END) / NULLIF(d.ANNUAL_BUDGET,0) * 100, 2) AS SALARY_BUDGET_PCT
FROM DEPARTMENTS d
LEFT JOIN EMPLOYEES e ON d.DEPT_ID = e.DEPT_ID
GROUP BY 1, 2, 3, 4, 5;

-- V_PAYROLL_TRENDS
-- Answers: monthly payroll cost, payroll by dept, bonus analysis
CREATE OR REPLACE VIEW V_PAYROLL_TRENDS AS
SELECT
    d.DEPT_NAME,
    p.PAY_PERIOD,
    TO_CHAR(p.PAY_PERIOD,'YYYY-MM')     AS PAY_MONTH,
    COUNT(DISTINCT p.EMP_ID)            AS EMPLOYEES_PAID,
    SUM(p.BASE_SALARY)                  AS TOTAL_BASE,
    SUM(p.BONUS_AMOUNT)                 AS TOTAL_BONUSES,
    SUM(p.OVERTIME_PAY)                 AS TOTAL_OVERTIME,
    SUM(p.DEDUCTIONS)                   AS TOTAL_DEDUCTIONS,
    SUM(p.NET_PAY)                      AS TOTAL_NET_PAY,
    AVG(p.NET_PAY)                      AS AVG_NET_PAY
FROM PAYROLL p
JOIN DEPARTMENTS d ON p.DEPT_ID = d.DEPT_ID
GROUP BY 1, 2, 3;

-- V_PERFORMANCE_SUMMARY
-- Answers: avg ratings by dept/quarter, top performers, review trends
CREATE OR REPLACE VIEW V_PERFORMANCE_SUMMARY AS
SELECT
    d.DEPT_NAME,
    pr.REVIEW_PERIOD,
    COUNT(DISTINCT pr.EMP_ID)           AS EMPLOYEES_REVIEWED,
    ROUND(AVG(pr.RATING), 2)            AS AVG_RATING,
    MIN(pr.RATING)                      AS MIN_RATING,
    MAX(pr.RATING)                      AS MAX_RATING,
    ROUND(AVG(pr.GOALS_MET_PCT), 2)     AS AVG_GOALS_MET_PCT,
    COUNT(CASE WHEN pr.RATING >= 4.0 THEN 1 END) AS HIGH_PERFORMERS,
    COUNT(CASE WHEN pr.RATING < 2.5  THEN 1 END) AS LOW_PERFORMERS
FROM PERFORMANCE_REVIEWS pr
JOIN DEPARTMENTS d ON pr.DEPT_ID = d.DEPT_ID
GROUP BY 1, 2;

-- ════════════════════════════════════════════════════════════
-- FINANCE SEMANTIC VIEWS
-- ════════════════════════════════════════════════════════════
USE SCHEMA FINANCE;

-- V_BUDGET_VS_ACTUAL
-- Answers: budget vs actual spend, variance by dept/month
CREATE OR REPLACE VIEW V_BUDGET_VS_ACTUAL AS
SELECT
    d.DEPT_NAME,
    a.ACCOUNT_NAME,
    a.ACCOUNT_TYPE,
    a.ACCOUNT_CATEGORY,
    b.BUDGET_YEAR,
    b.BUDGET_MONTH,
    TO_DATE(b.BUDGET_YEAR || '-' || LPAD(b.BUDGET_MONTH::VARCHAR,2,'0') || '-01') AS BUDGET_PERIOD,
    SUM(b.BUDGET_AMOUNT)                        AS BUDGET_AMOUNT,
    SUM(b.REVISED_AMOUNT)                       AS REVISED_BUDGET,
    SUM(b.ACTUAL_AMOUNT)                        AS ACTUAL_AMOUNT,
    SUM(b.ACTUAL_AMOUNT - b.BUDGET_AMOUNT)      AS VARIANCE,
    ROUND(SUM(b.ACTUAL_AMOUNT) / NULLIF(SUM(b.BUDGET_AMOUNT),0) * 100, 2) AS ACTUAL_VS_BUDGET_PCT
FROM BUDGET_LINES b
JOIN CONVERSATIONAL_BI.HR.DEPARTMENTS d ON b.DEPT_ID  = d.DEPT_ID
JOIN GL_ACCOUNTS a                       ON b.ACCOUNT_ID = a.ACCOUNT_ID
GROUP BY 1, 2, 3, 4, 5, 6, 7;

-- V_EXPENSE_SUMMARY
-- Answers: expenses by category/dept/month, top vendors, approval rates
CREATE OR REPLACE VIEW V_EXPENSE_SUMMARY AS
SELECT
    d.DEPT_NAME,
    e.CATEGORY,
    e.VENDOR,
    DATE_TRUNC('MONTH', e.EXPENSE_DATE)         AS EXPENSE_MONTH,
    e.APPROVAL_STATUS,
    COUNT(e.EXPENSE_ID)                         AS EXPENSE_COUNT,
    SUM(e.AMOUNT)                               AS TOTAL_AMOUNT,
    AVG(e.AMOUNT)                               AS AVG_AMOUNT,
    SUM(CASE WHEN e.REIMBURSED THEN e.AMOUNT ELSE 0 END) AS REIMBURSED_AMOUNT,
    COUNT(CASE WHEN e.APPROVAL_STATUS = 'Approved' THEN 1 END) AS APPROVED_COUNT,
    COUNT(CASE WHEN e.APPROVAL_STATUS = 'Rejected' THEN 1 END) AS REJECTED_COUNT
FROM EXPENSES e
JOIN CONVERSATIONAL_BI.HR.DEPARTMENTS d ON e.DEPT_ID = d.DEPT_ID
GROUP BY 1, 2, 3, 4, 5;

-- V_INVOICE_AGING
-- Answers: outstanding invoices, overdue amounts, payment trends
CREATE OR REPLACE VIEW V_INVOICE_AGING AS
SELECT
    i.INVOICE_STATUS,
    DATE_TRUNC('MONTH', i.INVOICE_DATE)         AS INVOICE_MONTH,
    CASE
        WHEN i.INVOICE_STATUS = 'Paid'    THEN 'Paid'
        WHEN CURRENT_DATE() <= i.DUE_DATE THEN 'Current (not yet due)'
        WHEN DATEDIFF('DAY', i.DUE_DATE, CURRENT_DATE()) <= 30  THEN '1-30 days overdue'
        WHEN DATEDIFF('DAY', i.DUE_DATE, CURRENT_DATE()) <= 60  THEN '31-60 days overdue'
        WHEN DATEDIFF('DAY', i.DUE_DATE, CURRENT_DATE()) <= 90  THEN '61-90 days overdue'
        ELSE '90+ days overdue'
    END AS AGING_BUCKET,
    COUNT(i.INVOICE_ID)                         AS INVOICE_COUNT,
    SUM(i.TOTAL_DUE)                            AS TOTAL_DUE,
    SUM(i.PAID_AMOUNT)                          AS TOTAL_PAID,
    SUM(i.TOTAL_DUE - i.PAID_AMOUNT)            AS OUTSTANDING_BALANCE,
    AVG(DATEDIFF('DAY', i.INVOICE_DATE, COALESCE(i.PAYMENT_DATE, CURRENT_DATE()))) AS AVG_DAYS_TO_PAY
FROM INVOICES i
GROUP BY 1, 2, 3;

-- ════════════════════════════════════════════════════════════
-- ADDITIONAL SALES SEMANTIC VIEWS
-- ════════════════════════════════════════════════════════════
USE SCHEMA SALES;

CREATE OR REPLACE VIEW V_INVENTORY_STATUS AS
SELECT
    p.PRODUCT_NAME,
    p.CATEGORY,
    s.STORE_NAME,
    s.REGION,
    inv.SNAPSHOT_DATE,
    inv.QUANTITY_ON_HAND,
    inv.QUANTITY_RESERVED,
    inv.REORDER_POINT,
    inv.LAST_RESTOCKED,
    IFF(inv.QUANTITY_ON_HAND <= inv.REORDER_POINT, 'REORDER', 'OK') AS STOCK_STATUS
FROM INVENTORY inv
JOIN PRODUCTS p ON inv.PRODUCT_ID = p.PRODUCT_ID
JOIN STORES s ON inv.STORE_ID = s.STORE_ID
WHERE inv.SNAPSHOT_DATE = (SELECT MAX(SNAPSHOT_DATE) FROM INVENTORY);

CREATE OR REPLACE VIEW V_STORE_PERFORMANCE AS
SELECT
    s.STORE_NAME,
    s.CITY,
    s.REGION,
    DATE_TRUNC('MONTH', o.ORDER_DATE) AS ORDER_MONTH,
    COUNT(o.ORDER_ID)                 AS ORDER_COUNT,
    SUM(o.TOTAL_AMOUNT)               AS TOTAL_REVENUE,
    AVG(o.TOTAL_AMOUNT)               AS AVG_ORDER_VALUE,
    COUNT(DISTINCT o.CUSTOMER_ID)     AS UNIQUE_CUSTOMERS
FROM ORDERS o
JOIN STORES s ON o.STORE_ID = s.STORE_ID
WHERE o.STATUS != 'Cancelled'
GROUP BY 1, 2, 3, 4;
