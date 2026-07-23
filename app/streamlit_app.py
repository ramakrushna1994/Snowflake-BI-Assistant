import streamlit as st
from snowflake.snowpark.context import get_active_session
import pandas as pd
import re

st.set_page_config(page_title="DataForge", layout="wide")
st.title("DataForge")
st.caption("Conversational BI powered by Snowflake Cortex — Sales · HR · Finance")

# ── Semantic view registry ─────────────────────────────────────────────────
SEMANTIC_VIEWS = {
    "CONVERSATIONAL_BI.SALES.V_MONTHLY_REVENUE": "Monthly revenue trend, revenue by month or year, order volume over time, average order value trends",
    "CONVERSATIONAL_BI.SALES.V_PRODUCT_PERFORMANCE": "Top or bottom products, product revenue, units sold, product margin, return rate by product, revenue by category or subcategory",
    "CONVERSATIONAL_BI.SALES.V_CUSTOMER_SEGMENTS": "Revenue by region or segment, top customers, customer lifetime value, customer spending, days since last order",
    "CONVERSATIONAL_BI.SALES.V_RETURN_ANALYSIS": "Return rates, return reasons, refunds by product or category, return trends by month",
    "CONVERSATIONAL_BI.SALES.V_CHANNEL_PERFORMANCE": "Sales by channel, channel mix, online vs retail revenue, channel order volume",
    "CONVERSATIONAL_BI.HR.V_DEPT_SUMMARY": "Headcount by department, average salary, salary vs budget, department size, min max salary",
    "CONVERSATIONAL_BI.HR.V_PAYROLL_TRENDS": "Monthly payroll cost, total payroll by department, bonus amounts, overtime pay, net pay trends",
    "CONVERSATIONAL_BI.HR.V_PERFORMANCE_SUMMARY": "Average performance rating by department or quarter, high performers, low performers, goals met percentage",
    "CONVERSATIONAL_BI.FINANCE.V_BUDGET_VS_ACTUAL": "Budget vs actual spend, variance by department or month, over or under budget, budget utilisation",
    "CONVERSATIONAL_BI.FINANCE.V_EXPENSE_SUMMARY": "Expenses by category or department, top vendors, approval rates, reimbursement amounts, monthly expense trends",
    "CONVERSATIONAL_BI.FINANCE.V_INVOICE_AGING": "Outstanding invoices, overdue balances, invoice aging buckets, days to pay, payment trends",
}


# ── 1. Live schema metadata ────────────────────────────────────────────────

def get_live_schema(session):
    rows = session.sql("""
        SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE
        FROM CONVERSATIONAL_BI.INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA IN ('SALES','HR','FINANCE')
        ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION
    """).collect()
    tables = {}
    for r in rows:
        fqn = f"CONVERSATIONAL_BI.{r['TABLE_SCHEMA']}.{r['TABLE_NAME']}"
        tables.setdefault(fqn, []).append(f"  - {r['COLUMN_NAME']} ({r['DATA_TYPE']})")
    lines = []
    for tbl, cols in tables.items():
        lines.append(tbl)
        lines.extend(cols)
    return "\n".join(lines)


def build_sql_prompt(question, schema_context):
    return f"""You are a SQL generator for Snowflake. Translate the user question into a valid Snowflake SQL query.

Current database schema (live — use ONLY these tables and columns):
{schema_context}

Rules:
1. Return ONLY the SQL query. No explanation. No markdown. No code fences.
2. Use fully qualified table names exactly as shown above.
3. Use ORDER BY + LIMIT for top N questions.
4. Use SUM/AVG/COUNT for aggregation questions.
5. For revenue use ORDER_ITEMS (QUANTITY * UNIT_PRICE) or LINE_TOTAL.
6. For payroll questions use the PAYROLL table.
7. For budget questions use BUDGET_LINES joined with GL_ACCOUNTS and DEPARTMENTS.

User question: {question}"""


# ── 2. Semantic view matcher ───────────────────────────────────────────────

def match_semantic_view(session, question):
    view_list = "\n".join([f"- {v}: {desc}" for v, desc in SEMANTIC_VIEWS.items()])
    prompt = f"""You are a query router. Given a user question, decide if it can be answered directly from one of the pre-built semantic views below.

User question: {question}

Available semantic views:
{view_list}

If the question matches a view, reply with ONLY the fully qualified view name (e.g. CONVERSATIONAL_BI.SALES.V_MONTHLY_REVENUE).
If no view matches well, reply with exactly: NONE"""
    prompt_escaped = prompt.replace("'", "''")
    result = session.sql(
        f"SELECT SNOWFLAKE.CORTEX.COMPLETE('mistral-large2', '{prompt_escaped}') AS R"
    ).collect()[0]["R"].strip()
    # Extract view name if present
    for view in SEMANTIC_VIEWS:
        if view in result:
            return view
    return None


# ── 3. SQL Confidence scoring ──────────────────────────────────────────────

def score_sql(session, question, sql, schema_context):
    prompt = f"""You are a SQL quality reviewer. Score the SQL query below on 3 criteria.

User question: {question}

Generated SQL:
{sql}

Available schema:
{schema_context}

Score each criterion from 1 to 10 and give a one-line reason. Use EXACTLY this format:
RELEVANCE: <score>/10 | <reason>
SCHEMA_COMPLIANCE: <score>/10 | <reason>
SQL_QUALITY: <score>/10 | <reason>
VERDICT: <GOOD or NEEDS REVIEW or RISKY>

Scoring guide:
- RELEVANCE: Does the SQL correctly answer the user question?
- SCHEMA_COMPLIANCE: Are all table/column names valid per the schema above?
- SQL_QUALITY: Correct JOINs, proper aggregations, no SELECT *, reasonable LIMIT?
- VERDICT: GOOD if all scores >= 8, NEEDS REVIEW if any score 5-7, RISKY if any score < 5"""

    prompt_escaped = prompt.replace("'", "''")
    raw = session.sql(
        f"SELECT SNOWFLAKE.CORTEX.COMPLETE('mistral-large2', '{prompt_escaped}') AS R"
    ).collect()[0]["R"].strip()

    result = {"relevance": 0, "relevance_reason": "", "schema_compliance": 0,
              "schema_compliance_reason": "", "sql_quality": 0, "sql_quality_reason": "",
              "verdict": "NEEDS REVIEW", "raw": raw}

    for line in raw.splitlines():
        line = line.strip()
        m = re.match(r"RELEVANCE:\s*(\d+)/10\s*\|\s*(.+)", line)
        if m: result["relevance"] = int(m.group(1)); result["relevance_reason"] = m.group(2).strip()
        m = re.match(r"SCHEMA_COMPLIANCE:\s*(\d+)/10\s*\|\s*(.+)", line)
        if m: result["schema_compliance"] = int(m.group(1)); result["schema_compliance_reason"] = m.group(2).strip()
        m = re.match(r"SQL_QUALITY:\s*(\d+)/10\s*\|\s*(.+)", line)
        if m: result["sql_quality"] = int(m.group(1)); result["sql_quality_reason"] = m.group(2).strip()
        m = re.match(r"VERDICT:\s*(GOOD|NEEDS REVIEW|RISKY)", line)
        if m: result["verdict"] = m.group(1)
    return result


def render_confidence(scores):
    verdict = scores["verdict"]
    st.markdown("#### Confidence Score")
    if verdict == "GOOD":
        st.success(f"Confidence: {verdict}")
    elif verdict == "NEEDS REVIEW":
        st.warning(f"Confidence: {verdict}")
    else:
        st.error(f"Confidence: {verdict}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Relevance", f"{scores['relevance']}/10", help=scores["relevance_reason"])
    c2.metric("Schema Fit", f"{scores['schema_compliance']}/10", help=scores["schema_compliance_reason"])
    c3.metric("SQL Quality", f"{scores['sql_quality']}/10", help=scores["sql_quality_reason"])
    with st.expander("Confidence details"):
        st.markdown(f"- **Relevance:** {scores['relevance_reason']}")
        st.markdown(f"- **Schema Fit:** {scores['schema_compliance_reason']}")
        st.markdown(f"- **SQL Quality:** {scores['sql_quality_reason']}")


# ── 4. Query runner ────────────────────────────────────────────────────────

def run_query(session, sql):
    try:
        return pd.DataFrame(session.sql(sql).collect()), None
    except Exception as e:
        return None, str(e)


def render_chart(df):
    if df is None or df.empty or len(df.columns) < 2:
        return
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    if not numeric_cols:
        return
    non_numeric = [c for c in df.columns if c not in numeric_cols]
    try:
        if non_numeric and len(df) > 1:
            st.bar_chart(df.set_index(non_numeric[0])[numeric_cols[:2]])
        elif len(df) > 1:
            st.line_chart(df[numeric_cols[:2]])
    except Exception:
        pass


# ── 5. Sidebar ─────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Example Questions")
    examples = [
        "Monthly revenue trend for last 6 months?",
        "Top 5 products by revenue?",
        "Revenue by customer segment?",
        "Which channel has highest order volume?",
        "Average salary by department?",
        "Monthly payroll cost by department?",
        "Which departments are over budget?",
        "Top expense categories this year?",
        "Invoice aging — how much is overdue?",
        "Return rate by product category?",
    ]
    for ex in examples:
        if st.button(ex, key=f"ex_{ex}"):
            st.session_state["q"] = ex

    st.divider()
    st.subheader("Semantic Views")
    for v in SEMANTIC_VIEWS:
        st.caption(v.split(".")[-1])

    st.divider()
    if st.button("Refresh Schema"):
        st.session_state.pop("schema_context", None)
        st.session_state.pop("schema_table", None)
    if "schema_table" in st.session_state:
        st.dataframe(st.session_state["schema_table"], use_container_width=True)


# ── 6. Input ────────────────────────────────────────────────────────────────

default_q = st.session_state.get("q", "")
question = st.text_input("Ask a question:", value=default_q, key="question_input")
ask_clicked = st.button("Ask", type="primary")


# ── 7. Process ──────────────────────────────────────────────────────────────

if ask_clicked and question.strip():
    st.session_state["q"] = ""
    session = get_active_session()

    # Load schema once per session
    if "schema_context" not in st.session_state:
        with st.spinner("Loading live schema..."):
            try:
                st.session_state["schema_context"] = get_live_schema(session)
                rows = session.sql("""
                    SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE
                    FROM CONVERSATIONAL_BI.INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA IN ('SALES','HR','FINANCE')
                    ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION
                """).collect()
                st.session_state["schema_table"] = pd.DataFrame(rows)
            except Exception as e:
                st.error(f"Schema load error: {e}")
                st.stop()

    schema_context = st.session_state["schema_context"]

    st.markdown("---")
    st.markdown(f"**Q: {question}**")

    # Step 1: Check semantic views first
    matched_view = None
    try:
        with st.spinner("Checking semantic views..."):
            matched_view = match_semantic_view(session, question)
    except Exception:
        pass

    if matched_view:
        st.info(f"Answered from semantic view: `{matched_view.split('.')[-1]}`")
        query_sql = f"SELECT * FROM {matched_view} LIMIT 500"
        with st.expander("Query", expanded=False):
            st.code(query_sql, language="sql")

        with st.spinner("Running query..."):
            df, error = run_query(session, query_sql)

        if error:
            st.error(f"Query error: {error}")
            st.stop()

    else:
        # Step 2: Generate SQL via LLM
        try:
            with st.spinner("Generating SQL..."):
                prompt = build_sql_prompt(question, schema_context)
                prompt_escaped = prompt.replace("'", "''")
                result = session.sql(
                    f"SELECT SNOWFLAKE.CORTEX.COMPLETE('mistral-large2', '{prompt_escaped}') AS R"
                ).collect()
                generated_sql = result[0]["R"].strip()
                if "```" in generated_sql:
                    lines = [l for l in generated_sql.split("\n") if not l.strip().startswith("```")]
                    generated_sql = "\n".join(lines).strip()
        except Exception as e:
            st.error(f"SQL generation error: {e}")
            st.stop()

        with st.expander("Generated SQL", expanded=True):
            st.code(generated_sql, language="sql")

        # Step 3: Confidence score
        try:
            with st.spinner("Scoring confidence..."):
                scores = score_sql(session, question, generated_sql, schema_context)
            render_confidence(scores)
        except Exception as e:
            st.warning(f"Confidence scoring unavailable: {e}")

        # Step 4: Run query
        with st.spinner("Running query..."):
            df, error = run_query(session, generated_sql)

        if error:
            st.error(f"Query error: {error}")
            st.stop()

    if df is None or df.empty:
        st.warning("Query returned no results.")
        st.stop()

    st.dataframe(df, use_container_width=True)
    render_chart(df)

    # Step 5: Summary
    try:
        with st.spinner("Generating summary..."):
            results_str = df.head(20).to_string(index=False)
            summary_prompt = f"""You are a data analyst presenting results to a business audience.
The user asked: "{question}"
The query returned these results:
{results_str}

Write a structured summary with:
- A one-sentence headline finding (bold it with **)
- 3 bullet points highlighting the most important numbers or trends
- One short actionable insight or recommendation

Use clear, plain business language. No SQL. No technical jargon."""
            sp_escaped = summary_prompt.replace("'", "''")
            summary = session.sql(
                f"SELECT SNOWFLAKE.CORTEX.COMPLETE('mistral-large2', '{sp_escaped}') AS R"
            ).collect()[0]["R"].strip()
        st.markdown("#### Summary")
        st.markdown(summary)
    except Exception as e:
        st.warning(f"Summary unavailable: {e}")

elif not ask_clicked:
    st.markdown("Type a question above and click **Ask**.")
