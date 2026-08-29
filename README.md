# DataForge — Conversational BI Assistant

> Built for **Coco Quest** — Snowflake Northstar Event, Bhubaneswar, 2026

A natural language BI assistant powered by Snowflake Cortex. Ask business questions in plain English and get SQL-generated results with confidence scoring, charts, and AI summaries — all running natively inside Snowflake.

---

## Features

- **Natural Language to SQL** — Powered by Snowflake Cortex (`llama3.3-70b`)
- **Single-Call Generation** — One LLM call produces the query and reports which semantic view (if any) it drew from
- **Semantic View Preference** — 13 pre-aggregated, fan-out-safe views the model queries directly when one fits, so common questions avoid multi-table joins — while still applying the filters, ordering, and limits the question asked for
- **Live Schema Metadata** — Tables *and* views fetched dynamically from `INFORMATION_SCHEMA` at runtime; handles schema evolution and drift automatically
- **SQL Safety Guardrails** — Generated SQL is validated to be a single SELECT; DDL/DML keywords (DROP, DELETE, INSERT, ALTER, etc.) are blocked before execution. String literals are excluded from the scan, so legitimate values like `'Needs update'` aren't misread as commands
- **Row Limiting** — Appends `LIMIT 500` unless the query already ends with a row cap (a `LIMIT` inside a CTE caps the CTE, not the result)
- **Self-Repair** — If Snowflake rejects the generated SQL, the error is fed back for a single repair attempt, re-validated, and retried
- **Confidence Scoring** — Every generated SQL is scored on Relevance (LLM), Schema Compliance (code-verified against live schema), and SQL Quality (LLM) with a GOOD / NEEDS REVIEW / RISKY verdict
- **Prompt Injection Defense** — User questions are wrapped in delimiters with explicit instructions to treat content as data, not commands; question display uses `st.write` to prevent markdown injection in the UI
- **Auto Charts** — Bar and line charts rendered automatically for numeric results; failures surface a user-visible message instead of silently passing
- **AI Summaries** — Grounded business summaries that only state facts supported by the result data
- **Session Caching** — Snowpark session and schema metadata are cached in `st.session_state` to avoid redundant round-trips
- **Streamlit in Snowflake** — No external hosting required; runs entirely inside your Snowflake account

---

## Screenshots

| Ask a question | SQL + Confidence Score | Chart Output |
|---|---|---|
| *(add screenshot)* | *(add screenshot)* | *(add screenshot)* |

> To add screenshots: run the app in Snowsight, capture the three key screens, and drop them into `docs/screenshots/`. Then replace the cells above with `![description](docs/screenshots/filename.png)`.

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

Pre-aggregated, fan-out-safe views the generator prefers when one fits the question:

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
| `SALES.V_INVENTORY_STATUS` | Stock levels, low-stock alerts, reorder status by product/store |
| `SALES.V_STORE_PERFORMANCE` | Revenue and orders by store, AOV, unique customers per store |

### Data Correctness & Design Notes

The semantic views and seed scripts follow two rules that protect metric accuracy:

- **No join fan-out.** Views that combine a header grain (orders, products, customers)
  with a detail grain (order items, returns) pre-aggregate each child in its own CTE
  before joining. This prevents one-to-many joins from multiplying `SUM`/`AVG` measures
  (e.g. revenue inflated by the number of returns). Applies to `V_MONTHLY_REVENUE`,
  `V_PRODUCT_PERFORMANCE`, `V_CUSTOMER_SEGMENTS`, and `V_CHANNEL_PERFORMANCE`.
- **Deterministic identities for referential integrity.** Fact/dimension tables use
  `CREATE OR REPLACE TABLE`, which resets each `AUTOINCREMENT` primary key to `1..N` on
  every run. Child foreign keys are seeded with `UNIFORM(1, N)`, so they only resolve if
  parent IDs start at 1. (Using `TRUNCATE` instead does **not** reset the identity
  sequence in Snowflake — repeated runs drift the IDs past the `UNIFORM` range and silently
  break every join.) Because the scripts are a regenerable demo seed, `CREATE OR REPLACE`
  is both idempotent and correct.
- **Internally consistent amounts.** Derived money columns are computed, not randomised:
  `ORDER_ITEMS.LINE_TOTAL = QTY × PRICE × (1 − discount)`,
  `INVOICES.TOTAL_DUE = INVOICE_AMOUNT + TAX_AMOUNT`, and `PAID_AMOUNT`/status/payment-date
  are mutually consistent (no negative balances or overpayments).

---

## Production Considerations

This project is a competition demo. Before using in production:

- **Authentication**: Add Snowflake OAuth or SSO; the current build uses session-level credentials
- **Rate limiting**: Cortex LLM calls are unbounded — add per-user quotas to control cost
- **Cost controls**: `LIMIT 500` guards against runaway row scans, but large semantic view queries can still be expensive; add warehouse auto-suspend (60s idle) and set a statement timeout
- **Schema isolation**: Semantic views hard-code schema names (`SALES`, `HR`, `FINANCE`) — parameterize for multi-tenant or multi-environment deployments
- **Prompt injection**: Delimiter-based defense is a first layer; add server-side input validation and length limits for production traffic
- **Monitoring**: Wire Cortex usage logs to Snowflake `QUERY_HISTORY` for per-user cost attribution; set up a spend alert in Snowflake Resource Monitors

---

## Setup & Deployment

### Prerequisites
- Snowflake account with ACCOUNTADMIN role
- Cortex LLM access (`llama3.3-70b` must be available in your region)

**Verify Cortex availability** — run this in a Snowsight worksheet:

```sql
SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.3-70b', 'ping');
```

If it returns a response, you're good. If you get an error (model unavailable in your region), change the model constant in `app/prompts.py`:

```python
CORTEX_MODEL = "mistral-large2"  # fallback if llama3.3-70b is unavailable
```

Other supported fallback models: `llama3.1-70b`, `llama3.1-8b`, `mistral-7b`, `gemma-7b`. Check [Cortex LLM availability](https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions#availability) for your region.

> The model must reliably return the JSON contract `{"sql": ..., "view": ...}`. Smaller
> fallbacks (`llama3.1-8b`, `mistral-7b`, `gemma-7b`) are more likely to drift into prose;
> the parser recovers bare SQL, but the semantic-view badge will stop appearing.

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

## CI/CD — Automatic Deployment

This project uses **GitHub Actions** for automated deployments to Snowflake.

### Streamlit App (`app/`)
- **Trigger:** Push to `main` that changes files in `app/`
- **Workflow:** `.github/workflows/deploy-streamlit.yml`
- **Action:** Automatically uploads all app files to `@CONVERSATIONAL_BI.APP.STREAMLIT_STAGE`
- **Approval:** None required (safe — only uploads Python files)

### Setup Scripts (`setup/`)
- **Trigger:** Push to `main` that changes files in `setup/`
- **Workflow:** `.github/workflows/deploy-setup.yml`
- **Action:** Executes only the changed SQL scripts against Snowflake
- **Approval:** Requires manual approval in the `production` environment before executing (since scripts contain DDL/DML)

**Setup required:**
1. Add GitHub Secrets (Settings → Secrets → Actions):
   | Secret | Value |
   |--------|-------|
   | `SNOWFLAKE_ACCOUNT` | Your Snowflake account identifier |
   | `SNOWFLAKE_PASSWORD` | Password for the deploying user |

2. Create a GitHub Environment called `production` (Settings → Environments → New environment):
   - Enable "Required reviewers" and add yourself as a reviewer
   - This gates setup script execution behind manual approval

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
| LLM | Snowflake Cortex (`llama3.3-70b`) |
| UI | Streamlit in Snowflake |
| CI/CD | GitHub Actions + Snow CLI |
| Schema Discovery | `INFORMATION_SCHEMA.COLUMNS` |
| Data Generation | Snowflake `TABLE(GENERATOR())` |
| Version Control | Git / GitHub |

---

## Project Structure

```
Snowflake-BI-Assistant/
├── .github/
│   └── workflows/
│       ├── tests.yml            # CI: offline unit tests (no Snowflake, no credits)
│       ├── deploy-streamlit.yml  # CI/CD: auto-deploy app on push to main
│       └── deploy-setup.yml      # CI/CD: run changed SQL scripts (with approval)
├── app/
│   ├── streamlit_app.py        # UI shell — layout, session state, rendering
│   ├── prompts.py              # All prompt-builder functions
│   ├── query_engine.py         # Schema fetch, SQL gen, validation, scoring, execution
│   └── snowflake.yml           # Snow CLI deployment config
├── tests/
│   └── test_query_engine.py    # Offline tests for guardrails + response parsing
├── sample_questions.txt        # 100 complex analytical questions for evaluation
├── setup/
│   ├── 01_create_database.sql  # Database, schemas, warehouse
│   ├── 02_sales_data.sql       # Initial Sales tables
│   ├── 03_hr_data.sql          # Initial HR tables
│   ├── 04_setup_streamlit.sql  # Streamlit app object
│   ├── 05_expand_sales.sql     # High-volume Sales data
│   ├── 06_expand_hr.sql        # Expanded HR + Payroll
│   ├── 07_finance_schema.sql   # Finance schema
│   └── 08_semantic_views.sql   # 13 semantic views
└── README.md
```
