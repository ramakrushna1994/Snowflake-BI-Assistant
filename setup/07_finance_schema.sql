-- ============================================================
-- 07_finance_schema.sql
-- New FINANCE schema: GL_ACCOUNTS, COST_CENTERS, BUDGET_LINES,
-- INVOICES, INVOICE_LINES, EXPENSES
-- ============================================================

USE DATABASE CONVERSATIONAL_BI;
USE WAREHOUSE BI_ASSISTANT_WH;

CREATE SCHEMA IF NOT EXISTS CONVERSATIONAL_BI.FINANCE;
USE SCHEMA FINANCE;

-- ── GL_ACCOUNTS (50 rows) ─────────────────────────────────
CREATE OR REPLACE TABLE GL_ACCOUNTS (
    ACCOUNT_ID      INT AUTOINCREMENT PRIMARY KEY,
    ACCOUNT_CODE    VARCHAR(10),
    ACCOUNT_NAME    VARCHAR(100),
    ACCOUNT_TYPE    VARCHAR(30),   -- Revenue, Expense, Asset, Liability
    ACCOUNT_CATEGORY VARCHAR(50),
    IS_ACTIVE       BOOLEAN DEFAULT TRUE
);

INSERT INTO GL_ACCOUNTS (ACCOUNT_CODE, ACCOUNT_NAME, ACCOUNT_TYPE, ACCOUNT_CATEGORY) VALUES
('4001','Product Revenue','Revenue','Sales'),
('4002','Service Revenue','Revenue','Sales'),
('4003','Subscription Revenue','Revenue','Sales'),
('4004','Other Revenue','Revenue','Other'),
('5001','Cost of Goods Sold','Expense','COGS'),
('5002','Shipping & Fulfilment','Expense','COGS'),
('5003','Packaging','Expense','COGS'),
('6001','Salaries & Wages','Expense','Payroll'),
('6002','Bonuses','Expense','Payroll'),
('6003','Benefits & Insurance','Expense','Payroll'),
('6004','Payroll Taxes','Expense','Payroll'),
('6005','Contract Labour','Expense','Payroll'),
('7001','Rent & Facilities','Expense','Facilities'),
('7002','Utilities','Expense','Facilities'),
('7003','Office Supplies','Expense','Facilities'),
('7004','Equipment Lease','Expense','Facilities'),
('7005','Maintenance & Repair','Expense','Facilities'),
('8001','Software & SaaS','Expense','Technology'),
('8002','Hardware','Expense','Technology'),
('8003','Cloud Infrastructure','Expense','Technology'),
('8004','IT Support','Expense','Technology'),
('9001','Marketing & Advertising','Expense','Marketing'),
('9002','Events & Sponsorships','Expense','Marketing'),
('9003','PR & Communications','Expense','Marketing'),
('9004','Market Research','Expense','Marketing'),
('10001','Travel & Entertainment','Expense','T&E'),
('10002','Meals & Entertainment','Expense','T&E'),
('10003','Conference & Training','Expense','T&E'),
('11001','Legal & Compliance','Expense','G&A'),
('11002','Audit & Accounting','Expense','G&A'),
('11003','Insurance','Expense','G&A'),
('11004','Banking & Finance Charges','Expense','G&A'),
('12001','Depreciation','Expense','Non-Cash'),
('12002','Amortisation','Expense','Non-Cash'),
('13001','Interest Income','Revenue','Other'),
('13002','Interest Expense','Expense','Financing'),
('14001','Cash & Equivalents','Asset','Current'),
('14002','Accounts Receivable','Asset','Current'),
('14003','Inventory','Asset','Current'),
('14004','Prepaid Expenses','Asset','Current'),
('15001','Property & Equipment','Asset','Non-Current'),
('15002','Intangible Assets','Asset','Non-Current'),
('16001','Accounts Payable','Liability','Current'),
('16002','Accrued Liabilities','Liability','Current'),
('16003','Deferred Revenue','Liability','Current'),
('16004','Short-Term Debt','Liability','Current'),
('17001','Long-Term Debt','Liability','Non-Current'),
('17002','Equity','Liability','Equity'),
('18001','Tax Payable','Liability','Current'),
('18002','Income Tax Expense','Expense','Tax');

-- ── COST_CENTERS (15 rows) ────────────────────────────────
CREATE OR REPLACE TABLE COST_CENTERS (
    CC_ID       INT AUTOINCREMENT PRIMARY KEY,
    CC_CODE     VARCHAR(20),
    CC_NAME     VARCHAR(100),
    DEPT_ID     INT,
    CC_MANAGER  VARCHAR(100)
);

INSERT INTO COST_CENTERS (CC_CODE, CC_NAME, DEPT_ID, CC_MANAGER) VALUES
('CC-ENG-1','Engineering - Core Platform',1,'Sarah Chen'),
('CC-ENG-2','Engineering - Data Infra',1,'Robert Singh'),
('CC-ENG-3','Engineering - Product Dev',1,'Emily Rodriguez'),
('CC-SAL-1','Sales - Enterprise',2,'Chris Wang'),
('CC-SAL-2','Sales - SMB',2,'Ryan Davis'),
('CC-MKT-1','Marketing - Digital',3,'Samantha Green'),
('CC-MKT-2','Marketing - Brand & Events',3,'Brandon Cole'),
('CC-HR-1','Human Resources - All',4,'Linda Wright'),
('CC-FIN-1','Finance - FP&A',5,'Catherine Young'),
('CC-FIN-2','Finance - Accounting',5,'Derek Phillips'),
('CC-OPS-1','Operations - Logistics',6,'Patrick Reed'),
('CC-OPS-2','Operations - Facilities',6,'Monica Flores'),
('CC-CSX-1','Customer Success',7,'Angela Kim'),
('CC-PM-1','Product Management',8,'Priya Sharma'),
('CC-DA-1','Data & Analytics',10,'Andrew Carter');

-- ── BUDGET_LINES (dept x account x month = ~3000 rows) ────
CREATE OR REPLACE TABLE BUDGET_LINES (
    BUDGET_ID   INT AUTOINCREMENT PRIMARY KEY,
    DEPT_ID     INT,
    ACCOUNT_ID  INT,
    CC_ID       INT,
    BUDGET_YEAR INT,
    BUDGET_MONTH INT,           -- 1-12
    BUDGET_AMOUNT DECIMAL(14,2),
    REVISED_AMOUNT DECIMAL(14,2),
    ACTUAL_AMOUNT  DECIMAL(14,2)
);

INSERT INTO BUDGET_LINES (DEPT_ID,ACCOUNT_ID,CC_ID,BUDGET_YEAR,BUDGET_MONTH,BUDGET_AMOUNT,REVISED_AMOUNT,ACTUAL_AMOUNT)
SELECT
    UNIFORM(1,10,RANDOM())   AS DEPT_ID,
    UNIFORM(6,50,RANDOM())   AS ACCOUNT_ID,
    UNIFORM(1,15,RANDOM())   AS CC_ID,
    CASE UNIFORM(1,2,RANDOM()) WHEN 1 THEN 2024 ELSE 2025 END AS BUDGET_YEAR,
    UNIFORM(1,12,RANDOM())   AS BUDGET_MONTH,
    ROUND(UNIFORM(5000,200000,RANDOM())::DECIMAL(14,2),2) AS BUDGET_AMOUNT,
    ROUND(UNIFORM(4000,210000,RANDOM())::DECIMAL(14,2),2) AS REVISED_AMOUNT,
    ROUND(UNIFORM(3000,220000,RANDOM())::DECIMAL(14,2),2) AS ACTUAL_AMOUNT
FROM TABLE(GENERATOR(ROWCOUNT => 3000));

-- ── INVOICES (2000 rows) ──────────────────────────────────
CREATE OR REPLACE TABLE INVOICES (
    INVOICE_ID      INT AUTOINCREMENT PRIMARY KEY,
    INVOICE_NUMBER  VARCHAR(20),
    CUSTOMER_ID     INT,
    ORDER_ID        INT,
    INVOICE_DATE    DATE,
    DUE_DATE        DATE,
    INVOICE_AMOUNT  DECIMAL(12,2),
    TAX_AMOUNT      DECIMAL(10,2),
    TOTAL_DUE       DECIMAL(12,2),
    PAID_AMOUNT     DECIMAL(12,2),
    INVOICE_STATUS  VARCHAR(20),   -- Draft, Sent, Paid, Overdue, Void
    PAYMENT_DATE    DATE
);

-- NOTE: amounts are derived so the ledger is internally consistent:
--   TOTAL_DUE   = INVOICE_AMOUNT + TAX_AMOUNT
--   PAID_AMOUNT is driven by INVOICE_STATUS (Paid = fully paid, else unpaid)
--   PAYMENT_DATE is only set for Paid invoices
INSERT INTO INVOICES (INVOICE_NUMBER,CUSTOMER_ID,ORDER_ID,INVOICE_DATE,DUE_DATE,INVOICE_AMOUNT,TAX_AMOUNT,TOTAL_DUE,PAID_AMOUNT,INVOICE_STATUS,PAYMENT_DATE)
WITH base AS (
    SELECT
        'INV-' || LPAD(SEQ4()::VARCHAR,6,'0')          AS INVOICE_NUMBER,
        UNIFORM(1,500,RANDOM())                         AS CUSTOMER_ID,
        UNIFORM(1,5000,RANDOM())                        AS ORDER_ID,
        DATEADD(DAY,-UNIFORM(0,730,RANDOM()),CURRENT_DATE()) AS INVOICE_DATE,
        ROUND(UNIFORM(100,10000,RANDOM())::DECIMAL(12,2),2) AS INVOICE_AMOUNT,
        CASE UNIFORM(1,5,RANDOM()) WHEN 1 THEN 'Overdue' WHEN 2 THEN 'Sent' WHEN 3 THEN 'Draft' WHEN 4 THEN 'Void' ELSE 'Paid' END AS INVOICE_STATUS
    FROM TABLE(GENERATOR(ROWCOUNT => 2000))
),
derived AS (
    SELECT
        INVOICE_NUMBER, CUSTOMER_ID, ORDER_ID, INVOICE_DATE,
        DATEADD(DAY, UNIFORM(15,60,RANDOM()), INVOICE_DATE) AS DUE_DATE,
        INVOICE_AMOUNT,
        ROUND(INVOICE_AMOUNT * 0.08, 2)                 AS TAX_AMOUNT,
        INVOICE_STATUS
    FROM base
)
SELECT
    INVOICE_NUMBER,
    CUSTOMER_ID,
    ORDER_ID,
    INVOICE_DATE,
    DUE_DATE,
    INVOICE_AMOUNT,
    TAX_AMOUNT,
    INVOICE_AMOUNT + TAX_AMOUNT                          AS TOTAL_DUE,
    IFF(INVOICE_STATUS = 'Paid', INVOICE_AMOUNT + TAX_AMOUNT, 0) AS PAID_AMOUNT,
    INVOICE_STATUS,
    IFF(INVOICE_STATUS = 'Paid', DATEADD(DAY, UNIFORM(1,45,RANDOM()), INVOICE_DATE), NULL) AS PAYMENT_DATE
FROM derived;

-- ── INVOICE_LINES (6000 rows) ─────────────────────────────
CREATE OR REPLACE TABLE INVOICE_LINES (
    LINE_ID         INT AUTOINCREMENT PRIMARY KEY,
    INVOICE_ID      INT,
    PRODUCT_ID      INT,
    DESCRIPTION     VARCHAR(200),
    QUANTITY        INT,
    UNIT_PRICE      DECIMAL(10,2),
    LINE_AMOUNT     DECIMAL(12,2),
    ACCOUNT_ID      INT
);

INSERT INTO INVOICE_LINES (INVOICE_ID,PRODUCT_ID,DESCRIPTION,QUANTITY,UNIT_PRICE,LINE_AMOUNT,ACCOUNT_ID)
WITH lines AS (
    SELECT
        UNIFORM(1,2000,RANDOM())  AS INVOICE_ID,
        UNIFORM(1,96,RANDOM())    AS PRODUCT_ID,
        'Product / Service item ' || SEQ4() AS DESCRIPTION,
        UNIFORM(1,10,RANDOM())    AS QUANTITY,
        ROUND(UNIFORM(10,1500,RANDOM())::DECIMAL(10,2),2) AS UNIT_PRICE,
        CASE UNIFORM(1,3,RANDOM()) WHEN 1 THEN 1 WHEN 2 THEN 2 ELSE 3 END AS ACCOUNT_ID
    FROM TABLE(GENERATOR(ROWCOUNT => 6000))
)
SELECT
    INVOICE_ID,
    PRODUCT_ID,
    DESCRIPTION,
    QUANTITY,
    UNIT_PRICE,
    ROUND(QUANTITY * UNIT_PRICE, 2) AS LINE_AMOUNT,
    ACCOUNT_ID
FROM lines;

-- ── EXPENSES (3000 rows) ──────────────────────────────────
CREATE OR REPLACE TABLE EXPENSES (
    EXPENSE_ID      INT AUTOINCREMENT PRIMARY KEY,
    EMP_ID          INT,
    DEPT_ID         INT,
    CC_ID           INT,
    ACCOUNT_ID      INT,
    EXPENSE_DATE    DATE,
    AMOUNT          DECIMAL(10,2),
    CURRENCY        VARCHAR(5) DEFAULT 'USD',
    CATEGORY        VARCHAR(50),
    VENDOR          VARCHAR(100),
    DESCRIPTION     VARCHAR(200),
    APPROVAL_STATUS VARCHAR(20),  -- Pending, Approved, Rejected
    REIMBURSED      BOOLEAN DEFAULT FALSE
);

INSERT INTO EXPENSES (EMP_ID,DEPT_ID,CC_ID,ACCOUNT_ID,EXPENSE_DATE,AMOUNT,CATEGORY,VENDOR,DESCRIPTION,APPROVAL_STATUS,REIMBURSED)
SELECT
    UNIFORM(1,200,RANDOM())   AS EMP_ID,
    UNIFORM(1,10,RANDOM())    AS DEPT_ID,
    UNIFORM(1,15,RANDOM())    AS CC_ID,
    CASE UNIFORM(1,5,RANDOM()) WHEN 1 THEN 26 WHEN 2 THEN 27 WHEN 3 THEN 28 WHEN 4 THEN 16 ELSE 21 END AS ACCOUNT_ID,
    DATEADD(DAY,-UNIFORM(0,730,RANDOM()),CURRENT_DATE()) AS EXPENSE_DATE,
    ROUND(UNIFORM(10,5000,RANDOM())::DECIMAL(10,2),2)   AS AMOUNT,
    CASE UNIFORM(1,6,RANDOM())
        WHEN 1 THEN 'Travel'           WHEN 2 THEN 'Meals & Entertainment'
        WHEN 3 THEN 'Software'         WHEN 4 THEN 'Office Supplies'
        WHEN 5 THEN 'Training'         ELSE 'Marketing'
    END AS CATEGORY,
    CASE UNIFORM(1,8,RANDOM())
        WHEN 1 THEN 'Delta Airlines'   WHEN 2 THEN 'Marriott Hotels'
        WHEN 3 THEN 'AWS'              WHEN 4 THEN 'Salesforce'
        WHEN 5 THEN 'Zoom'             WHEN 6 THEN 'Uber'
        WHEN 7 THEN 'Amex Travel'      ELSE 'Office Depot'
    END AS VENDOR,
    'Expense item ' || SEQ4() AS DESCRIPTION,
    CASE UNIFORM(1,5,RANDOM()) WHEN 1 THEN 'Pending' WHEN 2 THEN 'Rejected' ELSE 'Approved' END AS APPROVAL_STATUS,
    IFF(UNIFORM(1,3,RANDOM())<3, TRUE, FALSE) AS REIMBURSED
FROM TABLE(GENERATOR(ROWCOUNT => 3000));
