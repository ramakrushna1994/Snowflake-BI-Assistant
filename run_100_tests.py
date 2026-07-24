"""
DataForge 100-Question Stress Test
===================================
Runs 100 complex questions through the full DataForge pipeline on EN42638:
  question → Cortex prompt → LLM → SQL → validate → execute → record

Usage:
    set SF_PASSWORD=your_password
    python run_100_tests.py

Output: test_results.csv  +  console summary
"""

import os, sys, re, json, time, csv, textwrap
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
ACCOUNT   = "uzhhplf-en42638"
USER      = "RAMAKRUSHNA"
PASSWORD  = "Trishika#0804231"
WAREHOUSE = "BI_ASSISTANT_WH"
DATABASE  = "CONVERSATIONAL_BI"
MODEL     = "mistral-large2"
ROW_LIMIT = 500

# ── 100 Test questions ─────────────────────────────────────────────────────────
QUESTIONS = [
    # ─── SALES – Revenue & Orders ────────────────────────────────────────────
    ("SALES", "What is the monthly revenue trend for the last 12 months?"),
    ("SALES", "Show total revenue and order count for each month in the last 6 months."),
    ("SALES", "What is the year-over-year revenue growth comparing this year to last year?"),
    ("SALES", "Which month had the highest gross revenue in the past 2 years?"),
    ("SALES", "What is the average order value per month for the last year?"),
    ("SALES", "Show revenue breakdown by week for the last 8 weeks."),
    ("SALES", "What is the total discount amount given per channel per month?"),
    ("SALES", "How does net revenue compare to gross revenue by month?"),
    ("SALES", "What percentage of orders were cancelled each month?"),
    ("SALES", "Show total orders and revenue by order status."),

    # ─── SALES – Products ────────────────────────────────────────────────────
    ("SALES", "Top 5 products by total net revenue?"),
    ("SALES", "Which 10 products have the highest gross margin percentage?"),
    ("SALES", "List the bottom 5 products by units sold this year."),
    ("SALES", "Which product categories generate the most revenue?"),
    ("SALES", "Show revenue and return rate for each product subcategory."),
    ("SALES", "Which products have a return rate above 15%?"),
    ("SALES", "What are the top 3 products in each category by revenue?"),
    ("SALES", "Which products have the highest unit cost and lowest margin?"),
    ("SALES", "Show total units sold and net revenue per product for Electronics."),
    ("SALES", "Which products have never been ordered?"),
    ("SALES", "Compare gross revenue vs net revenue for the top 10 products."),
    ("SALES", "What is the average unit price vs unit cost for each category?"),

    # ─── SALES – Customers ───────────────────────────────────────────────────
    ("SALES", "Who are the top 10 customers by lifetime value?"),
    ("SALES", "Show average order value and total orders per customer segment."),
    ("SALES", "Which customer segment has the highest lifetime value per customer?"),
    ("SALES", "How many customers in each region placed orders last quarter?"),
    ("SALES", "Which customers have not ordered in the last 90 days?"),
    ("SALES", "What is the revenue distribution across Enterprise, Mid-Market and SMB segments?"),
    ("SALES", "Show customer count and average lifetime value by acquisition channel."),
    ("SALES", "Which 5 customers have the highest number of returns?"),
    ("SALES", "What is the average days since last order for each segment?"),
    ("SALES", "Show total revenue and average order value by state, top 10 states."),

    # ─── SALES – Channels & Stores ───────────────────────────────────────────
    ("SALES", "Which sales channel has the highest total order volume?"),
    ("SALES", "Compare average order value across all sales channels."),
    ("SALES", "What is the monthly revenue trend for each channel?"),
    ("SALES", "Which channel has the highest total discounts given?"),
    ("SALES", "Show unique customer count and revenue by channel type (Online/Retail/Wholesale)."),
    ("SALES", "Which stores have the highest revenue this quarter?"),
    ("SALES", "Show top 5 stores by average order value."),
    ("SALES", "What is the revenue per store by region?"),

    # ─── SALES – Returns & Inventory ─────────────────────────────────────────
    ("SALES", "What is the return rate by product category?"),
    ("SALES", "Which return reason is most common?"),
    ("SALES", "Show total refund amount and return count by month."),
    ("SALES", "Which products have the most returns in the last 6 months?"),
    ("SALES", "What is the total refund amount by return status?"),
    ("SALES", "Which products are running low on stock (below reorder point)?"),
    ("SALES", "Show stores with the most low-stock products."),

    # ─── HR – Headcount & Salaries ────────────────────────────────────────────
    ("HR", "What is the average salary by department?"),
    ("HR", "Show headcount, average salary and total salary cost per department."),
    ("HR", "Which departments are over their headcount budget?"),
    ("HR", "Who are the top 5 highest paid employees?"),
    ("HR", "What is the salary range (min, max, avg) for each job level?"),
    ("HR", "Show employee count by job level and department."),
    ("HR", "Which departments have the highest total annual salary cost?"),
    ("HR", "How many employees are in each department?"),
    ("HR", "What is the average bonus percentage by department?"),
    ("HR", "Show employees hired in the last 12 months by department."),
    ("HR", "Which departments have the most senior employees (hired 5+ years ago)?"),
    ("HR", "What is the difference between actual headcount and headcount budget per department?"),
    ("HR", "Show salary distribution: how many employees earn above the company average?"),

    # ─── HR – Payroll ─────────────────────────────────────────────────────────
    ("HR", "What is the monthly payroll cost trend for the last 12 months?"),
    ("HR", "Show total base pay, bonus and overtime by department this year."),
    ("HR", "Which months had the highest overtime costs?"),
    ("HR", "What is the average monthly payroll cost per department?"),
    ("HR", "Show total bonuses paid by department and quarter."),
    ("HR", "Which departments have the highest overtime hours?"),

    # ─── HR – Performance & Attendance ────────────────────────────────────────
    ("HR", "What is the average performance rating by department?"),
    ("HR", "Which departments have the most employees rated below 3 out of 5?"),
    ("HR", "Show average performance score by job level."),
    ("HR", "Which departments have the highest absenteeism rate?"),
    ("HR", "Show total leave days taken by department this year."),
    ("HR", "What percentage of employees in each department met their goals?"),

    # ─── FINANCE – Invoices ───────────────────────────────────────────────────
    ("FINANCE", "Show invoice aging breakdown: current, 1-30 days, 31-60 days, 61-90 days, 90+ days overdue."),
    ("FINANCE", "What is the total outstanding balance by invoice status?"),
    ("FINANCE", "Which customers have the highest overdue invoice amounts?"),
    ("FINANCE", "What is the total invoiced amount vs total paid amount this year?"),
    ("FINANCE", "Show monthly invoice count and total value for the last 12 months."),
    ("FINANCE", "What is the average days to payment for paid invoices?"),
    ("FINANCE", "Which invoices have been outstanding for more than 90 days?"),
    ("FINANCE", "Show total outstanding balance grouped by customer."),
    ("FINANCE", "What percentage of invoices are paid vs overdue vs sent?"),
    ("FINANCE", "What is the average invoice amount by status?"),

    # ─── FINANCE – Budget & Expenses ──────────────────────────────────────────
    ("FINANCE", "Which departments are over budget this year?"),
    ("FINANCE", "Show budget vs actual spend and variance percentage by department."),
    ("FINANCE", "What is the total expense amount by category?"),
    ("FINANCE", "Which vendors have the highest total expenses?"),
    ("FINANCE", "Show monthly expense trend by top 5 categories."),
    ("FINANCE", "What is the expense approval rate by department?"),
    ("FINANCE", "Which departments have the highest budget utilisation percentage?"),
    ("FINANCE", "Show total reimbursed vs unreimbursed expenses by department."),
    ("FINANCE", "What are the top 10 most expensive expense entries this year?"),
    ("FINANCE", "Which cost centers are closest to their budget limit?"),

    # ─── COMPLEX / Cross-domain ───────────────────────────────────────────────
    ("COMPLEX", "Which product categories have both high revenue and high return rates?"),
    ("COMPLEX", "Show revenue per department employee (Sales revenue divided by HR headcount per dept)."),
    ("COMPLEX", "Which channels bring in the most revenue but also have the highest return rates?"),
    ("COMPLEX", "Compare monthly payroll cost growth rate vs monthly revenue growth rate."),
    ("COMPLEX", "Which customer segments have high lifetime value but also high return counts?"),
    ("COMPLEX", "Show departments that are both over headcount budget and over spend budget."),
    ("COMPLEX", "Which products have high sales volume but below-average gross margin?"),
    ("COMPLEX", "Show invoice aging summary alongside departmental budget variance."),
    ("COMPLEX", "Which months have both high sales revenue and high HR overtime costs?"),
    ("COMPLEX", "Show a scorecard: for each domain (Sales/HR/Finance) list one key metric."),
]

assert len(QUESTIONS) == 100, f"Expected 100 questions, got {len(QUESTIONS)}"

# ── Helpers ───────────────────────────────────────────────────────────────────

def connect():
    import snowflake.connector
    return snowflake.connector.connect(
        account=ACCOUNT, user=USER, password=PASSWORD,
        warehouse=WAREHOUSE, database=DATABASE, schema="APP",
        session_parameters={"QUERY_TAG": "dataforge_test"}
    )


def sf_query(conn, sql, params=None):
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur


def call_cortex(conn, prompt):
    escaped = prompt.replace("'", "''")
    cur = sf_query(conn, f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{MODEL}', '{escaped}') AS R")
    row = cur.fetchone()
    return row[0] if row else ""


def get_schema_context(conn):
    sql = """
        SELECT c.TABLE_SCHEMA, c.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE
        FROM CONVERSATIONAL_BI.INFORMATION_SCHEMA.COLUMNS c
        JOIN CONVERSATIONAL_BI.INFORMATION_SCHEMA.TABLES t
          ON c.TABLE_SCHEMA = t.TABLE_SCHEMA AND c.TABLE_NAME = t.TABLE_NAME
        WHERE c.TABLE_SCHEMA IN ('SALES','HR','FINANCE')
          AND t.TABLE_TYPE = 'BASE TABLE'
        ORDER BY c.TABLE_SCHEMA, c.TABLE_NAME, c.ORDINAL_POSITION
    """
    cur = sf_query(conn, sql)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    tables = {}
    for r in rows:
        row = dict(zip(cols, r))
        fqn = f"CONVERSATIONAL_BI.{row['TABLE_SCHEMA']}.{row['TABLE_NAME']}"
        tables.setdefault(fqn, []).append(f"  - {row['COLUMN_NAME']} ({row['DATA_TYPE']})")
    lines = []
    for tbl, tbl_cols in tables.items():
        lines.append(tbl)
        lines.extend(tbl_cols)
    return "\n".join(lines)


def build_prompt(question, schema_context):
    sys.path.insert(0, "app")
    from prompts import build_router_and_sql_prompt
    return build_router_and_sql_prompt(question, schema_context)


def extract_sql(raw):
    """Parse Cortex response: returns (mode, sql_or_view, confidence)."""
    raw = raw.strip()
    # Try JSON parse
    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            if "view" in data:
                return "VIEW", data["view"], data.get("confidence", "?")
            if "sql" in data:
                return "SQL", data["sql"].strip(), "LLM"
        except Exception:
            pass
    # Fallback: extract raw SQL block
    code_match = re.search(r'```(?:sql)?\s*(.*?)```', raw, re.DOTALL | re.IGNORECASE)
    if code_match:
        return "SQL", code_match.group(1).strip(), "LLM"
    if re.search(r'\bSELECT\b', raw, re.IGNORECASE):
        lines = [l for l in raw.splitlines() if re.search(r'\bSELECT|FROM|WHERE|GROUP\b', l, re.IGNORECASE)]
        return "SQL", "\n".join(lines).strip(), "LLM"
    return "UNROUTED", "", ""


def ensure_limit(sql, limit=ROW_LIMIT):
    if not re.search(r'\bLIMIT\b', sql, re.IGNORECASE):
        sql = sql.rstrip().rstrip(';') + f"\nLIMIT {limit}"
    return sql


def run_sql(conn, sql):
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description] if cur.description else []
    return rows, cols


DANGEROUS = re.compile(
    r'\b(DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE|GRANT|MERGE|CREATE|REVOKE|EXEC)\b',
    re.IGNORECASE
)


def validate(sql):
    if DANGEROUS.search(sql):
        return False, "Contains write/DDL keyword"
    if not re.search(r'\bSELECT\b', sql, re.IGNORECASE):
        return False, "No SELECT found"
    return True, "ok"


# ── Main test loop ─────────────────────────────────────────────────────────────

def run_tests():
    if not PASSWORD:
        print("\n[ERROR] SF_PASSWORD environment variable is not set.")
        sys.exit(1)

    domain_filter = os.environ.get("DOMAIN_FILTER", "").strip().upper()
    active_questions = [(d, q) for d, q in QUESTIONS
                        if not domain_filter or d == domain_filter]
    if domain_filter and not active_questions:
        print(f"[ERROR] No questions found for domain '{domain_filter}'")
        sys.exit(1)

    print(f"\n{'='*70}")
    print(f"  DataForge 100-Question Test  —  {datetime.now():%Y-%m-%d %H:%M}")
    print(f"  Account: {ACCOUNT}   Model: {MODEL}")
    print(f"{'='*70}\n")

    print("Connecting to Snowflake ...", end=" ", flush=True)
    conn = connect()
    print("OK")

    print("Fetching schema context ...", end=" ", flush=True)
    schema_context = get_schema_context(conn)
    print(f"OK  ({len(schema_context)} chars)\n")

    results = []
    domain_stats = {}

    for idx, (domain, question) in enumerate(active_questions, 1):
        t0 = time.time()
        row = {
            "n": idx, "domain": domain, "question": question,
            "mode": "", "sql": "", "rows": 0, "elapsed_s": 0,
            "status": "", "error": ""
        }

        short_q = textwrap.shorten(question, 60)
        print(f"[{idx:03d}/{len(active_questions)}] [{domain:7s}] {short_q} ... ", end="", flush=True)

        try:
            # 1. Build prompt and call Cortex
            prompt = build_prompt(question, schema_context)
            raw = call_cortex(conn, prompt)

            # 2. Parse response
            mode, target, confidence = extract_sql(raw)
            row["mode"] = mode

            if mode == "UNROUTED" or not target:
                row["status"] = "UNROUTED"
                print("UNROUTED")
            elif mode == "VIEW":
                final_sql = f"SELECT * FROM {target} LIMIT {ROW_LIMIT}"
                row["sql"] = final_sql
                ok, msg = validate(final_sql)
                if not ok:
                    row["status"] = "INVALID"; row["error"] = msg
                    print(f"INVALID  ({msg})")
                else:
                    rows, cols = run_sql(conn, final_sql)
                    row["rows"] = len(rows)
                    row["status"] = "PASS" if rows else "EMPTY"
                    print(f"VIEW/{confidence}  {len(rows)} rows  ({time.time()-t0:.1f}s)")
            else:  # SQL
                final_sql = ensure_limit(target)
                row["sql"] = final_sql
                ok, msg = validate(final_sql)
                if not ok:
                    row["status"] = "INVALID"; row["error"] = msg
                    print(f"INVALID  ({msg})")
                else:
                    rows, cols = run_sql(conn, final_sql)
                    row["rows"] = len(rows)
                    row["status"] = "PASS" if rows else "EMPTY"
                    print(f"SQL  {len(rows)} rows  ({time.time()-t0:.1f}s)")

        except Exception as e:
            row["status"] = "ERROR"
            row["error"] = str(e)[:120]
            print(f"ERROR  {row['error']}")

        row["elapsed_s"] = round(time.time() - t0, 2)
        results.append(row)

        # Track domain stats
        d = domain_stats.setdefault(domain, {"PASS":0,"EMPTY":0,"UNROUTED":0,"INVALID":0,"ERROR":0,"total":0,"time":0})
        d[row["status"]] = d.get(row["status"], 0) + 1
        d["total"] += 1
        d["time"] += row["elapsed_s"]

    conn.close()

    # ── Save CSV ──────────────────────────────────────────────────────────────
    csv_path = "test_results.csv"
    fieldnames = ["n","domain","question","status","mode","rows","elapsed_s","sql","error"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in results:
            w.writerow({k: r[k] for k in fieldnames})
    print(f"\nResults saved to {csv_path}")

    # ── Summary ───────────────────────────────────────────────────────────────
    total = len(results)
    pass_   = sum(1 for r in results if r["status"] == "PASS")
    empty   = sum(1 for r in results if r["status"] == "EMPTY")
    unrouted= sum(1 for r in results if r["status"] == "UNROUTED")
    invalid = sum(1 for r in results if r["status"] == "INVALID")
    error   = sum(1 for r in results if r["status"] == "ERROR")
    avg_t   = sum(r["elapsed_s"] for r in results) / total

    via_view = sum(1 for r in results if r["mode"] == "VIEW")
    via_sql  = sum(1 for r in results if r["mode"] == "SQL")

    print(f"\n{'='*70}")
    print(f"  OVERALL SUMMARY  ({total} questions)")
    print(f"{'='*70}")
    print(f"  PASS (has data) : {pass_:3d}  ({pass_/total*100:.0f}%)")
    print(f"  EMPTY (0 rows)  : {empty:3d}  ({empty/total*100:.0f}%)")
    print(f"  UNROUTED        : {unrouted:3d}  ({unrouted/total*100:.0f}%)")
    print(f"  INVALID SQL     : {invalid:3d}  ({invalid/total*100:.0f}%)")
    print(f"  ERROR           : {error:3d}  ({error/total*100:.0f}%)")
    print(f"  ─────────────────────────────────────────────")
    print(f"  Routed via VIEW : {via_view:3d}   via SQL : {via_sql:3d}")
    print(f"  Avg response    : {avg_t:.1f}s per question")
    print(f"{'='*70}")

    print(f"\n  BY DOMAIN:")
    print(f"  {'Domain':<10} {'Total':>6} {'PASS':>6} {'EMPTY':>6} {'FAIL':>6} {'Avg(s)':>7}")
    print(f"  {'-'*46}")
    for dom, s in domain_stats.items():
        fail = s.get("UNROUTED",0)+s.get("INVALID",0)+s.get("ERROR",0)
        avg = s["time"]/s["total"] if s["total"] else 0
        print(f"  {dom:<10} {s['total']:>6} {s.get('PASS',0):>6} {s.get('EMPTY',0):>6} {fail:>6} {avg:>7.1f}")
    print(f"{'='*70}\n")

    # ── Print failures for quick review ──────────────────────────────────────
    failures = [r for r in results if r["status"] not in ("PASS","EMPTY")]
    if failures:
        print(f"  FAILURES ({len(failures)}):")
        for r in failures:
            print(f"  [{r['n']:03d}] {r['status']:10s} {textwrap.shorten(r['question'],55)}")
            if r["error"]:
                print(f"             {r['error'][:80]}")
        print()


if __name__ == "__main__":
    run_tests()
