# DataForge — Conversational BI Assistant

A natural language BI assistant powered by Snowflake Cortex. Ask business questions in plain English and get SQL-generated results with confidence scoring, charts, and AI summaries — all running natively inside Snowflake.

---

## Features

- **Natural Language to SQL** — Powered by Snowflake Cortex (`mistral-large2`)
- **Single-Call Routing** — One LLM call decides whether to route to a semantic view (with HIGH/LOW confidence) or generate SQL directly
- **Semantic View Routing** — 11 pre-aggregated views for instant answers on common questions (no SQL generation needed)
- **Live Schema Metadata** — Schema fetched dynamically from `INFORMATION_SCHEMA` at runtime; handles schema evolution and drift automatically
- **SQL Safety Guardrails** — Generated SQL is validated to be SELECT-only; DDL/DML keywords (DROP, DELETE, INSERT, ALTER, etc.) are blocked before execution
- **Row Limiting** — Automatically appends `LIMIT 500` to generated queries missing an explicit limit
- **Confidence Scoring** — Every generated SQL is scored on Relevance (LLM), Schema Compliance (code-verified against live schema), and SQL Quality (LLM) with a GOOD / NEEDS REVIEW / RISKY verdict
- **Prompt Injection Defense** — User questions are wrapped in delimiters with explicit instructions to treat content as data, not commands
- **Auto Charts** — Bar and line charts rendered automatically for numeric results
- **AI Summaries** — Grounded business summaries that only state facts supported by the result data
- **Streamlit in Snowflake** — No external hosting required; runs entirely inside your Snowflake account

---

## Data Model

### SALES Schema
| Table | Description | Rows |
|-------|-------------|------|
| `PRODUCTS` | 96 products across Electronics, Furniture, Stationery, Appliances | 96 |
| `CUSTOMERS` | Customers with region, segment, acquisition channel | 500 |
| `ORDERS` | Orders with store, channel, promo, payment method | 5,000 |
| `ORDER_ITEMS` | Line-level order items with discount and line total | 15,000 |
| `RETURNS` | Return transactions with reason and refund amount | 1,500 |
| `INVENTORY` | Product × store × date stock snapshots | 10,000 |
| `STORES` | 20 physical store locations across US regions | 20 |
| `SALES_CHANNELS` | Online, Retail, Wholesale, Partner channels | 5 |
| `PROMOTIONS` | Discount codes and promotional campaigns | 15 |

### HR Schema
| Table | Description | Rows |
|-------|-------------|------|
| `EMPLOYEES` | 200 employees with salary, level, hire date | 200 |
| `DEPARTMENTS` | 10 departments with budget and headcount targets | 10 |
| `PAYROLL` | Monthly payroll per employee (24 months) | 4,800 |
| `PERFORMANCE_REVIEWS` | Quarterly reviews per employee (8 quarters) | 1,600 |
| `ATTENDANCE` | Weekly attendance per employee (104 weeks) | 20,800 |
| `JOB_HISTORY` | Promotions, transfers, salary changes | 300 |

### FINANCE Schema
| Table | Description | Rows |
|-------|-------------|------|
| `GL_ACCOUNTS` | Chart of accounts (Revenue, Expense, Asset, Liability) | 50 |
| `COST_CENTERS` | 15 cost centers mapped to departments | 15 |
| `BUDGET_LINES` | Monthly budget vs actual by dept and account | 3,000 |
| `INVOICES` | Customer invoices with status and aging | 2,000 |
| `INVOICE_LINES` | Line-level invoice items | 6,000 |
| `EXPENSES` | Employee expense reports with approval status | 3,000 |

---

## Semantic Views

Pre-aggregated views that bypass SQL generation for common question patterns:

| View | Answers |
|------|---------|
| `SALES.V_MONTHLY_REVENUE` | Monthly revenue trend, order volume, average order value |
| `SALES.V_PRODUCT_PERFORMANCE` | Top/bottom products, margin, units sold, return rate |
| `SALES.V_CUSTOMER_SEGMENTS` | Revenue by region/segment, customer LTV, churn signals |
| `SALES.V_RETURN_ANALYSIS` | Return rates, refund amounts, return reasons |
| `SALES.V_CHANNEL_PERFORMANCE` | Revenue and orders by sales channel |
| `HR.V_DEPT_SUMMARY` | Headcount, salary stats, budget utilisation per dept |
| `HR.V_PAYROLL_TRENDS` | Monthly payroll cost, bonuses, overtime by dept |
| `HR.V_PERFORMANCE_SUMMARY` | Avg ratings, high/low performers by dept and quarter |
| `FINANCE.V_BUDGET_VS_ACTUAL` | Budget vs actual spend, variance by dept/month |
| `FINANCE.V_EXPENSE_SUMMARY` | Expenses by category, vendor, approval rate |
| `FINANCE.V_INVOICE_AGING` | Outstanding invoices, aging buckets, days to pay |

---

## Setup & Deployment

### Prerequisites
- Snowflake account with ACCOUNTADMIN role
- Cortex LLM access (`mistral-large2` must be available in your region)

### Step 1 — Run Setup Scripts (in order)

Execute in Snowsight SQL worksheet:

```sql
-- 1. Create database, schemas, warehouse
-- File: setup/01_create_database.sql

-- 2. Load initial Sales data
-- File: setup/02_sales_data.sql

-- 3. Load initial HR data
-- File: setup/03_hr_data.sql

-- 4. Deploy Streamlit app object
-- File: setup/04_setup_streamlit.sql

-- 5. Expand Sales (high-volume with GENERATOR)
-- File: setup/05_expand_sales.sql

-- 6. Expand HR (Payroll, Attendance, Reviews)
-- File: setup/06_expand_hr.sql

-- 7. Create Finance schema
-- File: setup/07_finance_schema.sql

-- 8. Create all Semantic Views
-- File: setup/08_semantic_views.sql
```

### Step 2 — Upload the App

Using Snow CLI:

```bash
cd app
snow stage copy streamlit_app.py @CONVERSATIONAL_BI.APP.STREAMLIT_STAGE --overwrite
snow stage copy prompts.py @CONVERSATIONAL_BI.APP.STREAMLIT_STAGE --overwrite
snow stage copy query_engine.py @CONVERSATIONAL_BI.APP.STREAMLIT_STAGE --overwrite
```

Or via SQL worksheet:

```sql
PUT 'file:///path/to/app/streamlit_app.py'
  @CONVERSATIONAL_BI.APP.STREAMLIT_STAGE AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
PUT 'file:///path/to/app/prompts.py'
  @CONVERSATIONAL_BI.APP.STREAMLIT_STAGE AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
PUT 'file:///path/to/app/query_engine.py'
  @CONVERSATIONAL_BI.APP.STREAMLIT_STAGE AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
```

### Step 3 — Open in Snowsight

Navigate to **Snowsight → Streamlit → CONVERSATIONAL_BI.APP.CONVERSATIONAL_BI_ASSISTANT**

---

## Example Questions

**Sales**
- "Monthly revenue trend for last 6 months?"
- "Top 5 products by revenue?"
- "Which customer segment generates the most revenue?"
- "Return rate by product category?"
- "Revenue breakdown by sales channel?"

**HR**
- "Average salary by department?"
- "Monthly payroll cost by department?"
- "Which department has the most high performers?"
- "How many employees were hired in 2024?"

**Finance**
- "Which departments are over budget?"
- "Top expense categories this year?"
- "How much in overdue invoices do we have?"
- "Budget vs actual variance by department?"

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Database | Snowflake |
| LLM | Snowflake Cortex (`mistral-large2`) |
| UI | Streamlit in Snowflake |
| Schema Discovery | `INFORMATION_SCHEMA.COLUMNS` |
| Data Generation | Snowflake `TABLE(GENERATOR())` |
| Version Control | Git / GitHub |

---

## Project Structure

```
Snowflake-BI-Assistant/
├── app/
│   ├── streamlit_app.py        # UI shell — layout, session state, rendering
│   ├── prompts.py              # All prompt-builder functions
│   ├── query_engine.py         # Schema fetch, SQL gen, validation, scoring, execution
│   └── snowflake.yml           # Snow CLI deployment config
├── setup/
│   ├── 01_create_database.sql  # Database, schemas, warehouse
│   ├── 02_sales_data.sql       # Initial Sales tables
│   ├── 03_hr_data.sql          # Initial HR tables
│   ├── 04_setup_streamlit.sql  # Streamlit app object
│   ├── 05_expand_sales.sql     # High-volume Sales data
│   ├── 06_expand_hr.sql        # Expanded HR + Payroll
│   ├── 07_finance_schema.sql   # Finance schema
│   └── 08_semantic_views.sql   # 11 semantic views
└── README.md
```
