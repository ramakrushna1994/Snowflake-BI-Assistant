import streamlit as st
from snowflake.snowpark.context import get_active_session
import pandas as pd
import re

from prompts import SEMANTIC_VIEWS, CORTEX_MODEL, build_summary_prompt
from query_engine import (
    get_live_schema, generate_sql, validate_sql, ensure_limit,
    score_sql, run_query, check_value_compliance,
    save_correction, get_relevant_corrections,
)

st.set_page_config(page_title="DataForge", layout="wide")
st.title("DataForge")
st.caption("Conversational BI powered by Snowflake Cortex — Sales · HR · Finance")


# ── Sidebar ───────────────────────────────────────────────────────────────────

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
        "Which products are running low on stock?",
        "Which stores have the highest revenue this quarter?",
        "Which departments have the highest absenteeism?",
    ]
    for ex in examples:
        if st.button(ex, key=f"ex_{ex}"):
            # Set the widget value; the natural button-click rerun picks it up.
            # Do NOT call st.experimental_rerun() here — in SiS it fires before
            # the session-state write is committed and silently drops the value.
            st.session_state["question_input"] = ex

    st.divider()
    st.subheader("Semantic Views")
    for v in SEMANTIC_VIEWS:
        st.caption(v.split(".")[-1])

    st.divider()
    if st.button("Refresh Schema"):
        for key in ["schema_context", "schema_table", "known_identifiers", "enum_hints", "history", "errors", "session"]:
            st.session_state.pop(key, None)
        st.experimental_rerun()
    if "schema_table" in st.session_state:
        st.dataframe(st.session_state["schema_table"], use_container_width=True)

    if st.session_state.get("errors"):
        with st.expander(f"⚠️ {len(st.session_state['errors'])} routing error(s)"):
            for err in st.session_state["errors"]:
                st.caption(err)


# ── Input ─────────────────────────────────────────────────────────────────────

# The widget stores its value in st.session_state["question_input"]. Example
# buttons pre-fill by setting that key before rerun, so do NOT also pass value=
# (that would conflict with the Session State API and drop the pre-filled text).
question = st.text_input("Ask a question:", key="question_input")
ask_clicked = st.button("Ask", type="primary")


# ── Helpers ───────────────────────────────────────────────────────────────────

def render_confidence(scores):
    verdict = scores["verdict"]
    llm_ok  = scores.get("llm_scored", False)

    st.markdown("#### Confidence Score")
    if verdict == "GOOD":
        st.success(f"Confidence: {verdict}")
    elif verdict == "NEEDS REVIEW":
        st.warning(f"Confidence: {verdict}")
    elif verdict == "UNSCORED":
        st.info("Confidence: UNSCORED — LLM scoring output could not be parsed.")
    else:
        st.error(f"Confidence: {verdict}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Relevance",    f"{scores['relevance']}/10"          if llm_ok else "—",
              help=scores["relevance_reason"])
    c2.metric("Schema Fit",   f"{scores['schema_compliance']}/10",
              help=scores["schema_compliance_reason"])
    c3.metric("SQL Quality",  f"{scores['sql_quality']}/10"         if llm_ok else "—",
              help=scores["sql_quality_reason"])
    c4.metric("Value Check",  f"{scores.get('value_compliance', '—')}/10",
              help=scores.get("value_compliance_reason", "Not checked"))

    if not llm_ok:
        st.caption("Relevance & SQL Quality unavailable — only schema and value compliance scored.")

    if scores.get("bad_values"):
        st.warning(f"Suspicious values detected: {', '.join(repr(v) for v in scores['bad_values'][:5])}. "
                   "These may not exist in the database. Consider reporting this as a mistake below.")

    with st.expander("Confidence details"):
        st.markdown(f"- **Relevance:** {scores['relevance_reason']}")
        st.markdown(f"- **Schema Fit:** {scores['schema_compliance_reason']}")
        st.markdown(f"- **SQL Quality:** {scores['sql_quality_reason']}")
        st.markdown(f"- **Value Check:** {scores.get('value_compliance_reason', 'N/A')}")
        if scores.get("raw"):
            st.markdown("**Raw LLM output:**")
            st.text(scores["raw"])


def render_chart(df):
    if df is None or df.empty or len(df.columns) < 2:
        return
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    if not numeric_cols:
        return
    non_numeric = [c for c in df.columns if c not in numeric_cols]
    try:
        if non_numeric and len(df) > 1:
            first_col = df[non_numeric[0]]
            is_temporal = (
                pd.api.types.is_datetime64_any_dtype(first_col) or
                non_numeric[0].upper() in ("MONTH", "MONTH_LABEL", "PAY_MONTH",
                                            "REVENUE_MONTH", "BUDGET_PERIOD",
                                            "ORDER_MONTH", "RETURN_MONTH",
                                            "EXPENSE_MONTH", "INVOICE_MONTH")
            )
            chart_df = df.groupby(non_numeric[0])[numeric_cols[:2]].sum()
            if is_temporal or len(chart_df) > 12:
                st.line_chart(chart_df)
            else:
                st.bar_chart(chart_df)
        elif len(df) > 1:
            st.line_chart(df[numeric_cols[:2]])
    except Exception:
        st.caption("Chart not available for this result shape.")


# ── Main Processing ───────────────────────────────────────────────────────────

if ask_clicked and question.strip():
    if "session" not in st.session_state:
        st.session_state["session"] = get_active_session()
    session = st.session_state["session"]

    # Load schema once per session (single query, reused for text + table + identifiers)
    if "schema_context" not in st.session_state:
        with st.spinner("Loading live schema..."):
            try:
                schema_text, schema_df, known_ids, enum_hints = get_live_schema(session)
                st.session_state["schema_context"] = schema_text
                st.session_state["schema_table"] = schema_df
                st.session_state["known_identifiers"] = known_ids
                st.session_state["enum_hints"] = enum_hints
            except Exception as e:
                st.error(f"Schema load error: {e}")
                st.stop()

    schema_context = st.session_state["schema_context"]
    known_identifiers = st.session_state["known_identifiers"]

    if not schema_context.strip():
        st.error("Schema loaded empty. Verify SALES, HR, and FINANCE schemas exist and the app role has USAGE on INFORMATION_SCHEMA.")
        st.stop()

    # Display conversation history
    history = st.session_state.get("history", [])
    if history:
        st.markdown("#### Conversation History")
        for h in history[-3:]:
            with st.expander(f"Q: {h['question']}", expanded=False):
                st.code(h["sql"], language="sql")
                if h.get("summary"):
                    st.caption(h["summary"][:200])

    st.markdown("---")
    st.markdown(f"**Q:** {question}")

    # Step 1: Single LLM call — route to semantic view or generate SQL
    # Fetch relevant corrections to inject into prompt
    corrections = get_relevant_corrections(session, question)
    try:
        with st.spinner("Generating query..."):
            result = generate_sql(session, question, schema_context, SEMANTIC_VIEWS, history=history, corrections=corrections)
    except Exception as e:
        st.session_state.setdefault("errors", []).append(f"generate_sql: {e}")
        st.error(f"Query generation error: {e}")
        st.stop()

    if result.get("error") and result["type"] == "sql" and not result["value"]:
        st.error(f"Could not generate a query: {result['error']}")
        st.stop()

    scores = {}  # populated by generated SQL path; empty for view path

    if result["type"] == "view":
        view_name = result["value"]
        st.info(f"Answered from semantic view: `{view_name.split('.')[-1]}`")
        query_sql = f"SELECT * FROM {view_name} LIMIT 500"
        final_sql = query_sql
        with st.expander("Query", expanded=False):
            st.code(query_sql, language="sql")

        # Views are curated and reviewed — always HIGH confidence on schema fit
        st.markdown("#### Confidence Score")
        st.success("✅ Confidence: HIGH — curated semantic view")
        c1, c2, c3 = st.columns(3)
        c1.metric("Relevance",   "10/10", help="Routed to a purpose-built view for this question type.")
        c2.metric("Schema Fit",  "10/10", help="View is reviewed and maintained against the live schema.")
        c3.metric("SQL Quality", "10/10", help="Pre-validated SQL — no generation risk.")

        with st.spinner("Running query..."):
            df, error = run_query(session, query_sql)
        if error:
            st.error(f"Query error: {error}")
            st.stop()
    else:
        generated_sql = result["value"]
        # Strip markdown fences if present
        generated_sql = re.sub(r"```(?:sql)?", "", generated_sql).strip()

        # SQL safety guardrail
        is_valid, validation_error = validate_sql(generated_sql)
        if not is_valid:
            st.error(f"SQL blocked: {validation_error}")
            st.stop()

        # Ensure row limit
        generated_sql = ensure_limit(generated_sql)
        final_sql = generated_sql

        with st.expander("Generated SQL", expanded=True):
            st.code(generated_sql, language="sql")

        # Confidence scoring — score_sql never raises, always returns a dict
        scores = score_sql(session, question, generated_sql, known_identifiers)
        # Add value compliance check
        enum_hints = st.session_state.get("enum_hints", {})
        val_score, val_reason, bad_vals = check_value_compliance(generated_sql, enum_hints)
        scores["value_compliance"] = val_score
        scores["value_compliance_reason"] = val_reason
        scores["bad_values"] = bad_vals
        # Downgrade verdict if value compliance is poor
        if val_score < 5:
            scores["verdict"] = "RISKY"
        elif val_score < 8 and scores["verdict"] == "GOOD":
            scores["verdict"] = "NEEDS REVIEW"
        render_confidence(scores)

        # Execute query
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

    # Summary
    summary_text = ""
    try:
        with st.spinner("Generating summary..."):
            results_str = df.head(20).to_string(index=False)
            col_info = ", ".join(df.columns.tolist())
            summary_prompt = build_summary_prompt(question, results_str, col_info=col_info)
            sp_escaped = summary_prompt.replace("'", "''")
            summary = session.sql(
                f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{CORTEX_MODEL}', '{sp_escaped}') AS R"
            ).collect()[0]["R"]
            if not summary:
                raise ValueError("Cortex returned an empty response for summary.")
            summary = summary.strip()
            summary_text = summary
        st.markdown("#### Summary")
        st.markdown(summary)
    except Exception as e:
        st.warning(f"Summary unavailable: {e}")

    # Save to conversation history (cap at 3)
    st.session_state.setdefault("history", []).append({
        "question": question,
        "sql": final_sql,
        "summary": summary_text,
    })
    st.session_state["history"] = st.session_state["history"][-3:]

    # ── Learn from Mistake ────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Report a Mistake")
    st.caption("If the generated SQL was wrong, provide the correct version below. "
               "Future queries will learn from this correction.")

    with st.expander("Report Mistake", expanded=False):
        corrected_sql = st.text_area(
            "Corrected SQL",
            value=final_sql,
            height=150,
            key="correction_sql"
        )
        correction_reason = st.text_input(
            "What was wrong? (e.g., 'Used wrong status value')",
            key="correction_reason"
        )
        if st.button("Save Correction", type="secondary", key="save_correction"):
            if corrected_sql.strip() and corrected_sql.strip() != final_sql.strip():
                bad_vals_to_save = scores.get("bad_values", []) if result["type"] != "view" else []
                save_correction(
                    session, question, final_sql,
                    corrected_sql.strip(), correction_reason,
                    bad_values=bad_vals_to_save
                )
                st.success("Correction saved! Future queries will learn from this.")
            elif corrected_sql.strip() == final_sql.strip():
                st.warning("The corrected SQL is the same as the generated SQL. Please modify it.")
            else:
                st.warning("Please provide the corrected SQL.")

elif not ask_clicked:
    st.markdown("Type a question above and click **Ask**.")
elif ask_clicked and not question.strip():
    st.warning("Please enter a question before clicking Ask.")
