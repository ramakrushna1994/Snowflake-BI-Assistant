"""
DataForge Targeted Test Suite  — 25 representative questions
=============================================================
Covers every routing path (VIEW / SQL) and every domain (SALES / HR / FINANCE)
at ~15% of the cost of a full 100-question run.

Usage (GitHub Actions):  triggered via run-tests.yml
Local:  set SF_PASSWORD=... && python run_100_tests.py
"""

import os, sys, re, json, time, csv, textwrap
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
ACCOUNT   = "uzhhplf-en42638"
USER      = "RAMAKRUSHNA"
PASSWORD  = os.environ.get("SF_PASSWORD", "")
WAREHOUSE = "BI_ASSISTANT_WH"
DATABASE  = "CONVERSATIONAL_BI"
MODEL     = "mistral-large2"
ROW_LIMIT = 200          # smaller limit = less warehouse compute

# ── 25 Representative questions (one per domain × question-type) ───────────
QUESTIONS = [
    # ── SALES – should route to semantic views ────────────────────────────
    ("SALES-VIEW",  "What is the monthly revenue trend for the last 6 months?"),
    ("SALES-VIEW",  "Top 5 products by revenue?"),
    ("SALES-VIEW",  "Revenue by customer segment?"),
    ("SALES-VIEW",  "Which channel has the highest total order volume?"),
    ("SALES-VIEW",  "What is the return rate by product category?"),
    ("SALES-VIEW",  "Which products are running low on stock?"),
    ("SALES-VIEW",  "Which stores have the highest revenue this quarter?"),

    # ── SALES – complex queries that need SQL generation ──────────────────
    ("SALES-SQL",   "Show top 3 products in each category ranked by net revenue."),
    ("SALES-SQL",   "What is the month-over-month revenue growth rate for each of the last 6 months?"),
    ("SALES-SQL",   "Which customers placed more than 3 orders and have lifetime value over $3000?"),
    ("SALES-SQL",   "Show average order value by state, ranked highest to lowest, for the top 10 states."),

    # ── HR – should route to semantic views ───────────────────────────────
    ("HR-VIEW",     "Average salary by department?"),
    ("HR-VIEW",     "Monthly payroll cost by department?"),
    ("HR-VIEW",     "Which departments are over budget?"),
    ("HR-VIEW",     "What is the average performance rating by department?"),
    ("HR-VIEW",     "Which departments have the highest absenteeism rate?"),

    # ── HR – SQL generation ───────────────────────────────────────────────
    ("HR-SQL",      "Which employees earn more than 150% of their department average salary?"),
    ("HR-SQL",      "Show bonus payout as a percentage of base salary by job level."),

    # ── FINANCE – should route to semantic views ──────────────────────────
    ("FIN-VIEW",    "Show invoice aging breakdown: current, 30, 60, 90+ days overdue."),
    ("FIN-VIEW",    "Which departments are over budget this year?"),
    ("FIN-VIEW",    "Top expense categories this year?"),

    # ── FINANCE – SQL generation ──────────────────────────────────────────
    ("FIN-SQL",     "Which customers have total outstanding invoice balances above $5000?"),
    ("FIN-SQL",     "Show monthly expense growth rate for the last 6 months."),

    # ── COMPLEX – cross-domain, need SQL ─────────────────────────────────
    ("COMPLEX",     "Which product categories have both above-average revenue and above-average return rates?"),
    ("COMPLEX",     "Show departments that are simultaneously over headcount budget and over spend budget."),
]

assert len(QUESTIONS) == 25

# ── Helpers ───────────────────────────────────────────────────────────────────
def connect():
    import snowflake.connector
    return snowflake.connector.connect(
        account=ACCOUNT, user=USER, password=PASSWORD,
        warehouse=WAREHOUSE, database=DATABASE, schema="APP",
        session_parameters={"QUERY_TAG": "dataforge_test"}
    )

def sf_query(conn, sql):
    cur = conn.cursor()
    cur.execute(sql)
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
    raw = raw.strip()
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
    code_match = re.search(r'```(?:sql)?\s*(.*?)```', raw, re.DOTALL | re.IGNORECASE)
    if code_match:
        return "SQL", code_match.group(1).strip(), "LLM"
    if re.search(r'\bSELECT\b', raw, re.IGNORECASE):
        lines = [l for l in raw.splitlines()
                 if re.search(r'\bSELECT|FROM|WHERE|GROUP\b', l, re.IGNORECASE)]
        return "SQL", "\n".join(lines).strip(), "LLM"
    return "UNROUTED", "", ""

def ensure_limit(sql):
    if not re.search(r'\bLIMIT\b', sql, re.IGNORECASE):
        sql = sql.rstrip().rstrip(';') + f"\nLIMIT {ROW_LIMIT}"
    return sql

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

def run_sql(conn, sql):
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description] if cur.description else []
    return rows, cols

# ── Main ──────────────────────────────────────────────────────────────────────
def run_tests():
    if not PASSWORD:
        print("[ERROR] SF_PASSWORD not set.")
        sys.exit(1)

    total = len(QUESTIONS)
    print(f"\n{'='*65}")
    print(f"  DataForge Test Suite  —  {total} questions  —  {datetime.now():%Y-%m-%d %H:%M}")
    print(f"  Account: {ACCOUNT}    Model: {MODEL}")
    print(f"{'='*65}\n")

    print("Connecting ...", end=" ", flush=True)
    conn = connect()
    print("OK")
    print("Fetching schema ...", end=" ", flush=True)
    schema_context = get_schema_context(conn)
    print(f"OK ({len(schema_context)} chars)\n")

    results = []
    domain_stats = {}

    for idx, (domain, question) in enumerate(QUESTIONS, 1):
        t0 = time.time()
        row = {"n": idx, "domain": domain, "question": question,
               "mode": "", "sql": "", "rows": 0, "elapsed_s": 0,
               "status": "", "error": ""}

        short_q = textwrap.shorten(question, 55)
        print(f"[{idx:02d}/{total}] {domain:<10} {short_q} ", end="", flush=True)

        try:
            prompt = build_prompt(question, schema_context)
            raw    = call_cortex(conn, prompt)
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
                    row["status"] = "INVALID"; row["error"] = msg; print(f"INVALID ({msg})")
                else:
                    rows, _ = run_sql(conn, final_sql)
                    row["rows"] = len(rows)
                    row["status"] = "PASS" if rows else "EMPTY"
                    print(f"VIEW/{confidence:<4}  {len(rows):>4} rows  {time.time()-t0:.1f}s")
            else:
                final_sql = ensure_limit(target)
                row["sql"] = final_sql
                ok, msg = validate(final_sql)
                if not ok:
                    row["status"] = "INVALID"; row["error"] = msg; print(f"INVALID ({msg})")
                else:
                    rows, _ = run_sql(conn, final_sql)
                    row["rows"] = len(rows)
                    row["status"] = "PASS" if rows else "EMPTY"
                    print(f"SQL       {len(rows):>4} rows  {time.time()-t0:.1f}s")

        except Exception as e:
            row["status"] = "ERROR"
            row["error"]  = str(e)[:100]
            print(f"ERROR  {row['error']}")

        row["elapsed_s"] = round(time.time() - t0, 2)
        results.append(row)

        d = domain_stats.setdefault(domain, {"PASS":0,"EMPTY":0,"UNROUTED":0,"INVALID":0,"ERROR":0,"total":0,"time":0.0})
        d[row["status"]] += 1
        d["total"] += 1
        d["time"]  += row["elapsed_s"]

    conn.close()

    # Save CSV
    with open("test_results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["n","domain","question","status","mode","rows","elapsed_s","sql","error"])
        w.writeheader()
        for r in results:
            w.writerow({k: r[k] for k in ["n","domain","question","status","mode","rows","elapsed_s","sql","error"]})
    print("\nSaved → test_results.csv")

    # Summary
    passed   = sum(1 for r in results if r["status"] == "PASS")
    empty    = sum(1 for r in results if r["status"] == "EMPTY")
    failures = [r for r in results if r["status"] not in ("PASS","EMPTY")]
    avg_t    = sum(r["elapsed_s"] for r in results) / total
    via_view = sum(1 for r in results if r["mode"] == "VIEW")
    via_sql  = sum(1 for r in results if r["mode"] == "SQL")

    print(f"\n{'='*65}")
    print(f"  RESULTS: {passed}/{total} PASS   {empty} EMPTY   {len(failures)} FAIL   avg {avg_t:.1f}s/q")
    print(f"  Routing: {via_view} via VIEW   {via_sql} via SQL")
    print(f"{'='*65}")
    print(f"\n  {'Domain':<12} {'Total':>5} {'PASS':>5} {'EMPTY':>5} {'FAIL':>5} {'Avg s':>6}")
    print(f"  {'-'*40}")
    for dom, s in domain_stats.items():
        fail = s["UNROUTED"]+s["INVALID"]+s["ERROR"]
        print(f"  {dom:<12} {s['total']:>5} {s['PASS']:>5} {s['EMPTY']:>5} {fail:>5} {s['time']/s['total']:>6.1f}")
    if failures:
        print(f"\n  FAILURES:")
        for r in failures:
            print(f"    [{r['n']:02d}] {r['status']:<10} {textwrap.shorten(r['question'],50)}")
            if r["error"]:
                print(f"           {r['error'][:70]}")
    print()

if __name__ == "__main__":
    run_tests()
