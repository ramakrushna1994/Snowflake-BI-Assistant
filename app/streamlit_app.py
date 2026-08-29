import streamlit as st
from snowflake.snowpark.context import get_active_session
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from prompts import SEMANTIC_VIEWS, build_summary_prompt
from query_engine import (
    get_live_schema, generate_sql, repair_sql, validate_sql, ensure_limit,
    score_sql, run_query, check_value_compliance, complete,
    save_correction, get_relevant_corrections, format_sql,
)

# ── Page Config & Theme ──────────────────────────────────────────────────────

st.set_page_config(page_title="DataForge", page_icon="⚡", layout="wide")

st.markdown("""
<style>
    /* Main background */
    .stApp { background-color: #0e1117; }

    /* Chat message styling */
    [data-testid="stChatMessage"] {
        border-radius: 12px;
        margin-bottom: 0.75rem;
        padding: 1rem;
    }

    /* User messages */
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
        background: linear-gradient(135deg, #1a1f2e 0%, #1e2640 100%);
        border-left: 3px solid #29B5E8;
    }

    /* Assistant messages */
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
        background: linear-gradient(135deg, #151922 0%, #1a1f2e 100%);
        border-left: 3px solid #4ECB71;
    }

    /* Metric cards */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #1a1f2e 0%, #252b3b 100%);
        border: 1px solid #2d3548;
        border-radius: 10px;
        padding: 1rem;
    }
    [data-testid="stMetricValue"] { font-size: 1.3rem; }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #151922;
        border-radius: 10px;
        padding: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 8px 20px;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background-color: #29B5E8 !important;
        color: white !important;
    }

    /* Expander */
    [data-testid="stExpander"] {
        border: 1px solid #2d3548;
        border-radius: 10px;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d1117 0%, #151922 100%);
        border-right: 1px solid #2d3548;
    }
    section[data-testid="stSidebar"] h1 { font-size: 1.2rem; }

    /* Sidebar buttons */
    section[data-testid="stSidebar"] .stButton > button {
        background-color: transparent;
        border: 1px solid #2d3548;
        color: #c9d1d9;
        text-align: left;
        font-size: 0.85rem;
        transition: all 0.2s ease;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background-color: #1a2332;
        border-color: #29B5E8;
        color: #29B5E8;
    }

    /* Chat input */
    [data-testid="stChatInput"] textarea {
        border-radius: 12px !important;
        border: 1px solid #2d3548 !important;
        background-color: #151922 !important;
    }
    [data-testid="stChatInput"] textarea:focus {
        border-color: #29B5E8 !important;
        box-shadow: 0 0 0 1px #29B5E8 !important;
    }

    /* Plotly chart background */
    .js-plotly-plot .plotly .main-svg { background: transparent !important; }

    /* Info/warning/error banners */
    [data-testid="stAlert"] { border-radius: 8px; }

    /* Dataframe */
    [data-testid="stDataFrame"] {
        border: 1px solid #2d3548;
        border-radius: 8px;
    }

    /* Welcome header */
    .welcome-header {
        text-align: center;
        padding: 3rem 1rem 2rem;
        color: #c9d1d9;
    }
    .welcome-header h2 {
        background: linear-gradient(135deg, #29B5E8, #4ECB71);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 1.8rem;
        margin-bottom: 0.5rem;
    }
    .welcome-header p {
        color: #8b949e;
        font-size: 1rem;
    }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚡ DataForge")
    st.caption("Conversational BI powered by Snowflake Cortex")
    st.divider()

    st.markdown("##### 💬 Quick Questions")

    with st.expander("Sales & Revenue", expanded=True):
        for ex in [
            "Monthly revenue trend for last 6 months?",
            "Top 5 products by revenue?",
            "Revenue by customer segment?",
            "Which channel has highest order volume?",
            "Return rate by product category?",
            "Which stores have the highest revenue this quarter?",
        ]:
            if st.button(ex, key=f"ex_{ex}", use_container_width=True):
                st.session_state["pending_question"] = ex

    with st.expander("HR & Payroll"):
        for ex in [
            "Average salary by department?",
            "Monthly payroll cost by department?",
            "Which products are running low on stock?",
        ]:
            if st.button(ex, key=f"ex_{ex}", use_container_width=True):
                st.session_state["pending_question"] = ex

    with st.expander("Finance & Budget"):
        for ex in [
            "Which departments are over budget?",
            "Top expense categories this year?",
            "Invoice aging — how much is overdue?",
        ]:
            if st.button(ex, key=f"ex_{ex}", use_container_width=True):
                st.session_state["pending_question"] = ex

    st.divider()
    with st.expander("📊 Semantic Views"):
        for v in SEMANTIC_VIEWS:
            schema_label = v.split('.')[1]
            view_name = v.split('.')[-1].replace("V_", "").replace("_", " ").title()
            st.caption(f"{'📈' if schema_label == 'SALES' else '👥' if schema_label == 'HR' else '💰'} {view_name}")

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Refresh", use_container_width=True, help="Reload schema metadata"):
            for key in ["schema_context", "views_context", "schema_table",
                         "known_identifiers", "enum_hints", "data_year_range"]:
                st.session_state.pop(key, None)
            st.rerun()
    with col2:
        if st.button("🗑️ Clear Chat", use_container_width=True, help="Clear conversation"):
            st.session_state["messages"] = []
            st.session_state["history"] = []
            st.rerun()


# ── Session Init ─────────────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "history" not in st.session_state:
    st.session_state["history"] = []

if "session" not in st.session_state:
    st.session_state["session"] = get_active_session()
session = st.session_state["session"]


def load_schema():
    if "schema_context" not in st.session_state:
        schema_text, views_text, schema_df, known_ids, enum_hints, data_year_range = get_live_schema(session)
        st.session_state["schema_context"] = schema_text
        st.session_state["views_context"] = views_text
        st.session_state["schema_table"] = schema_df
        st.session_state["known_identifiers"] = known_ids
        st.session_state["enum_hints"] = enum_hints
        st.session_state["data_year_range"] = data_year_range
    elif "data_year_range" not in st.session_state:
        from query_engine import get_data_year_range
        st.session_state["data_year_range"] = get_data_year_range(session)


# ── Chart Builder ────────────────────────────────────────────────────────────

PLOTLY_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#e0e0e0"),
    margin=dict(l=40, r=20, t=40, b=40),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)

COLORS = ["#29B5E8", "#FF6B6B", "#4ECB71", "#FFD93D", "#C084FC", "#FB923C"]


def detect_chart_type(df, numeric_cols, non_numeric_cols):
    if not non_numeric_cols or not numeric_cols:
        return "table"

    label_col = non_numeric_cols[0]
    n_rows = len(df)
    first_col = df[label_col]

    is_temporal = (
        pd.api.types.is_datetime64_any_dtype(first_col)
        or label_col.upper() in (
            "MONTH", "MONTH_LABEL", "PAY_MONTH", "REVENUE_MONTH",
            "BUDGET_PERIOD", "ORDER_MONTH", "RETURN_MONTH",
            "EXPENSE_MONTH", "INVOICE_MONTH", "PAY_PERIOD",
            "REVIEW_PERIOD", "SNAPSHOT_DATE", "ORDER_DATE",
        )
    )

    is_proportion = (
        len(numeric_cols) == 1 and 2 <= n_rows <= 8
        and not is_temporal
    )

    if is_proportion:
        vals = df[numeric_cols[0]]
        if vals.min() >= 0 and vals.sum() > 0:
            return "pie"

    if is_temporal:
        return "line"

    if n_rows <= 15:
        return "bar"

    return "bar"


def build_chart(df):
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    if not numeric_cols:
        return None

    non_numeric = [c for c in df.columns if c not in numeric_cols]
    if not non_numeric:
        return None

    chart_type = detect_chart_type(df, numeric_cols, non_numeric)
    label_col = non_numeric[0]
    value_cols = numeric_cols[:3]

    if chart_type == "pie":
        fig = px.pie(
            df, names=label_col, values=value_cols[0],
            color_discrete_sequence=COLORS,
            hole=0.4,
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")

    elif chart_type == "line":
        fig = go.Figure()
        for i, col in enumerate(value_cols):
            fig.add_trace(go.Scatter(
                x=df[label_col], y=df[col],
                mode="lines+markers",
                name=col.replace("_", " ").title(),
                line=dict(color=COLORS[i % len(COLORS)], width=2.5),
                marker=dict(size=6),
            ))

    elif chart_type == "bar":
        if len(value_cols) == 1:
            fig = px.bar(
                df, x=label_col, y=value_cols[0],
                color_discrete_sequence=COLORS,
            )
        else:
            fig = go.Figure()
            for i, col in enumerate(value_cols):
                fig.add_trace(go.Bar(
                    x=df[label_col], y=df[col],
                    name=col.replace("_", " ").title(),
                    marker_color=COLORS[i % len(COLORS)],
                ))
            fig.update_layout(barmode="group")
    else:
        return None

    fig.update_layout(**PLOTLY_LAYOUT)
    return fig


# ── Confidence Renderer ──────────────────────────────────────────────────────

def render_confidence(scores):
    verdict = scores["verdict"]
    llm_ok = scores.get("llm_scored", False)

    label_map = {
        "GOOD": ("✅ High Confidence", "success"),
        "NEEDS REVIEW": ("⚠️ Needs Review", "warning"),
        "RISKY": ("🚨 Risky", "error"),
        "UNSCORED": ("❔ Unscored", "info"),
    }
    label, kind = label_map.get(verdict, ("❔ Unknown", "info"))
    getattr(st, kind)(label)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Relevance", f"{scores['relevance']}/10" if llm_ok else "—")
    c2.metric("Schema Fit", f"{scores['schema_compliance']}/10")
    c3.metric("SQL Quality", f"{scores['sql_quality']}/10" if llm_ok else "—")
    c4.metric("Value Check", f"{scores.get('value_compliance', '—')}/10")

    if scores.get("bad_values"):
        st.warning(
            f"Suspicious values: {', '.join(repr(v) for v in scores['bad_values'][:5])}"
        )

    with st.expander("Score details"):
        st.markdown(f"- **Relevance:** {scores['relevance_reason']}")
        st.markdown(f"- **Schema Fit:** {scores['schema_compliance_reason']}")
        st.markdown(f"- **SQL Quality:** {scores['sql_quality_reason']}")
        st.markdown(f"- **Value Check:** {scores.get('value_compliance_reason', 'N/A')}")


# ── Process Question ─────────────────────────────────────────────────────────

def process_question(question):
    load_schema()

    schema_context = st.session_state["schema_context"]
    views_context = st.session_state.get("views_context", "")
    known_identifiers = st.session_state["known_identifiers"]
    history = st.session_state.get("history", [])

    if not schema_context.strip():
        st.error("Schema loaded empty. Verify schemas exist and app role has USAGE.")
        return

    # Generate SQL
    corrections = get_relevant_corrections(session, question)
    data_year_range = st.session_state.get("data_year_range")
    with st.spinner("Generating query..."):
        try:
            result = generate_sql(
                session, question, schema_context, SEMANTIC_VIEWS,
                views_context=views_context, history=history,
                corrections=corrections,
                data_max_year=data_year_range,
            )
        except Exception as e:
            st.error(f"Query generation error: {e}")
            return

    if not result.get("sql"):
        st.error(f"Could not generate a query: {result.get('error') or 'empty response'}")
        return


    is_valid, validation_error = validate_sql(result["sql"])
    if not is_valid:
        st.error(f"SQL blocked: {validation_error}")
        return

    final_sql = ensure_limit(result["sql"])

    # Execute with one repair attempt
    with st.spinner("Running query..."):
        df, error = run_query(session, final_sql)

    if error:
        with st.spinner("Repairing query..."):
            try:
                repair = repair_sql(
                    session, question, final_sql, error,
                    schema_context, SEMANTIC_VIEWS, views_context=views_context,
                )
            except Exception as e:
                repair = {"sql": "", "view": None, "error": str(e)}

        repaired_sql = repair.get("sql")
        if repaired_sql:
            repair_valid, repair_error = validate_sql(repaired_sql)
            if repair_valid:
                repaired_sql = ensure_limit(repaired_sql)
                with st.spinner("Running repaired query..."):
                    retry_df, retry_error = run_query(session, repaired_sql)
                if not retry_error:
                    df, error, final_sql = retry_df, None, repaired_sql

    if error:
        st.error(f"Query error: {error}")
        return

    # Score
    scores = score_sql(session, question, final_sql, known_identifiers)
    enum_hints = st.session_state.get("enum_hints", {})
    val_score, val_reason, bad_vals = check_value_compliance(final_sql, enum_hints)
    scores["value_compliance"] = val_score
    scores["value_compliance_reason"] = val_reason
    scores["bad_values"] = bad_vals
    if val_score < 5:
        scores["verdict"] = "RISKY"
    elif val_score < 8 and scores["verdict"] == "GOOD":
        scores["verdict"] = "NEEDS REVIEW"

    has_data = df is not None and not df.empty

    if not has_data:
        st.warning("Query returned no results.")

    # Tabbed results — always show SQL & Quality, even on empty results
    if has_data:
        tab_data, tab_chart, tab_sql, tab_quality = st.tabs([
            "📊 Data", "📈 Chart", "🔍 SQL", "✅ Quality"
        ])
    else:
        tab_sql, tab_quality = st.tabs(["🔍 SQL", "✅ Quality"])

    if has_data:
        with tab_data:
            st.dataframe(df, use_container_width=True, height=min(len(df) * 38 + 50, 500))

        with tab_chart:
            fig = build_chart(df)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No chart available for this result shape.")

    with tab_sql:
        st.code(format_sql(final_sql), language="sql")

    with tab_quality:
        render_confidence(scores)

    # Summary with streaming effect (skip on empty results — saves a Cortex call)
    summary_text = ""
    if has_data:
        st.markdown("---")
        try:
            results_str = df.head(20).to_string(index=False)
            col_info = ", ".join(df.columns.tolist())
            summary_prompt = build_summary_prompt(question, results_str, col_info=col_info)
            summary_text = complete(session, summary_prompt)
            st.markdown("#### Summary")
            summary_container = st.empty()
            displayed = ""
            for i in range(0, len(summary_text), 3):
                displayed = summary_text[:i + 3]
                summary_container.markdown(displayed)
            summary_container.markdown(summary_text)
        except Exception as e:
            st.caption(f"Summary unavailable: {e}")

    # Save to history
    st.session_state["history"].append({
        "question": question, "sql": final_sql, "summary": summary_text,
    })
    st.session_state["history"] = st.session_state["history"][-5:]

    # Store for correction feature
    st.session_state["last_sql"] = final_sql
    st.session_state["last_question"] = question
    st.session_state["last_scores"] = scores

    # Correction
    with st.expander("Report a mistake"):
        corrected_sql = st.text_area("Corrected SQL", value=final_sql, height=120,
                                     key="correction_sql")
        correction_reason = st.text_input("What was wrong?", key="correction_reason")
        if st.button("Save Correction", key="save_correction"):
            if corrected_sql.strip() and corrected_sql.strip() != final_sql.strip():
                save_correction(
                    session, question, final_sql, corrected_sql.strip(),
                    correction_reason, bad_values=scores.get("bad_values", []),
                )
                st.success("Correction saved!")
            elif corrected_sql.strip() == final_sql.strip():
                st.warning("Corrected SQL is the same as generated SQL.")


# ── Chat UI ──────────────────────────────────────────────────────────────────

# Welcome screen when no messages
if not st.session_state["messages"]:
    st.markdown("""
    <div class="welcome-header">
        <h2>Welcome to DataForge</h2>
        <p>Ask questions about your Sales, HR, and Finance data in plain English.</p>
    </div>
    """, unsafe_allow_html=True)

    cols = st.columns(3)
    starters = [
        ("📈", "Sales", "Monthly revenue trend for last 6 months?"),
        ("👥", "HR", "Average salary by department?"),
        ("💰", "Finance", "Which departments are over budget?"),
    ]
    for col, (icon, label, q) in zip(cols, starters):
        with col:
            if st.button(f"{icon} {label}\n{q}", key=f"welcome_{label}", use_container_width=True):
                st.session_state["pending_question"] = q
                st.rerun()

# Display existing messages
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Handle sidebar example click
if "pending_question" in st.session_state:
    question = st.session_state.pop("pending_question")
    st.session_state["messages"].append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        process_question(question)
        st.session_state["messages"].append({
            "role": "assistant", "content": f"Answered: {question}",
        })

# Chat input
elif prompt := st.chat_input("Ask a question about your data..."):
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        process_question(prompt)
        st.session_state["messages"].append({
            "role": "assistant", "content": f"Answered: {prompt}",
        })
