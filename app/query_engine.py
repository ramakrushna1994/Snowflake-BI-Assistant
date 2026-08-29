"""Query engine: schema fetch, SQL generation, validation, scoring, execution (v2.2)."""

import re
import json
import logging
import pandas as pd

logger = logging.getLogger(__name__)


# Columns known to be categorical (low-cardinality enums worth exposing to the LLM)
_ENUM_CANDIDATES = [
    ("SALES", "ORDERS", "STATUS"),
    ("SALES", "ORDERS", "CHANNEL"),
    ("SALES", "ORDERS", "PAYMENT_METHOD"),
    ("SALES", "PRODUCTS", "CATEGORY"),
    ("SALES", "PRODUCTS", "SUBCATEGORY"),
    ("SALES", "CUSTOMERS", "REGION"),
    ("SALES", "CUSTOMERS", "SEGMENT"),
    ("SALES", "CUSTOMERS", "ACQUISITION_CHANNEL"),
    ("SALES", "RETURNS", "RETURN_REASON"),
    ("SALES", "SALES_CHANNELS", "CHANNEL_NAME"),
    ("HR", "EMPLOYEES", "DEPARTMENT"),
    ("HR", "EMPLOYEES", "JOB_LEVEL"),
    ("HR", "EMPLOYEES", "STATUS"),
    ("HR", "JOB_HISTORY", "CHANGE_TYPE"),
    ("FINANCE", "EXPENSES", "APPROVAL_STATUS"),
    ("FINANCE", "EXPENSES", "CATEGORY"),
    ("FINANCE", "EXPENSES", "VENDOR"),
    ("FINANCE", "INVOICES", "INVOICE_STATUS"),
    ("FINANCE", "GL_ACCOUNTS", "ACCOUNT_TYPE"),
    ("FINANCE", "GL_ACCOUNTS", "ACCOUNT_CATEGORY"),
    ("FINANCE", "BUDGET_LINES", "BUDGET_YEAR"),
    ("SALES", "RETURNS", "RETURN_STATUS"),
    ("HR", "EMPLOYEES", "EMPLOYMENT_TYPE"),
]


def get_enum_hints(session):
    """Fetch distinct values for known categorical columns. Returns dict of column -> values list."""
    enum_hints = {}
    for schema, table, column in _ENUM_CANDIDATES:
        try:
            rows = session.sql(
                f"SELECT DISTINCT {column} FROM CONVERSATIONAL_BI.{schema}.{table} "
                f"WHERE {column} IS NOT NULL ORDER BY {column} LIMIT 15"
            ).collect()
            values = [str(r[column]) for r in rows]
            if values:
                enum_hints[f"{schema}.{table}.{column}"] = values
        except Exception as e:
            # A missing column/table just means no hints for it — keep going,
            # but leave a trace so a systemic failure is diagnosable.
            logger.warning("enum sampling failed for %s.%s.%s: %s", schema, table, column, e)
    return enum_hints


def get_data_year_range(session):
    """Return (min_year, max_year) across key date/year columns, or None if unavailable."""
    try:
        row = session.sql("""
            SELECT MIN(y) AS MIN_YEAR, MAX(y) AS MAX_YEAR FROM (
                SELECT BUDGET_YEAR AS y FROM CONVERSATIONAL_BI.FINANCE.BUDGET_LINES
                UNION ALL
                SELECT YEAR(ORDER_DATE) FROM CONVERSATIONAL_BI.SALES.ORDERS
            )
        """).collect()
        if row:
            return int(row[0]["MIN_YEAR"]), int(row[0]["MAX_YEAR"])
    except Exception as e:
        logger.warning("data year range detection failed: %s", e)
    return None


def get_live_schema(session):
    """Fetch schema metadata once.

    Returns (schema_text, views_text, schema_df, known_identifiers, enum_hints, data_year_range).

    Views are fetched alongside base tables so the model can write targeted SQL
    against a semantic view (not just SELECT *), and so view columns count as
    known identifiers during compliance scoring.
    """
    rows = session.sql("""
        SELECT c.TABLE_SCHEMA, c.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE, t.TABLE_TYPE
        FROM CONVERSATIONAL_BI.INFORMATION_SCHEMA.COLUMNS c
        JOIN CONVERSATIONAL_BI.INFORMATION_SCHEMA.TABLES t
          ON c.TABLE_SCHEMA = t.TABLE_SCHEMA AND c.TABLE_NAME = t.TABLE_NAME
        WHERE c.TABLE_SCHEMA IN ('SALES','HR','FINANCE')
          AND t.TABLE_TYPE IN ('BASE TABLE','VIEW')
        ORDER BY c.TABLE_SCHEMA, c.TABLE_NAME, c.ORDINAL_POSITION
    """).collect()

    tables = {}
    views = {}
    known_identifiers = set()
    for r in rows:
        schema = r['TABLE_SCHEMA']
        table = r['TABLE_NAME']
        column = r['COLUMN_NAME']
        fqn = f"CONVERSATIONAL_BI.{schema}.{table}"
        target = views if r['TABLE_TYPE'] == 'VIEW' else tables
        target.setdefault(fqn, []).append((column, r['DATA_TYPE'], f"{schema}.{table}.{column}"))
        # Track identifiers for compliance checking
        known_identifiers.add(f"{schema}.{table}.{column}".upper())
        known_identifiers.add(f"CONVERSATIONAL_BI.{schema}.{table}.{column}".upper())
        known_identifiers.add(f"{table}.{column}".upper())
        known_identifiers.add(table.upper())
        known_identifiers.add(f"{schema}.{table}".upper())
        known_identifiers.add(f"CONVERSATIONAL_BI.{schema}.{table}".upper())
        known_identifiers.add(column.upper())

    # Fetch enum hints
    enum_hints = get_enum_hints(session)

    def _render(objects):
        lines = []
        for obj, cols in objects.items():
            lines.append(obj)
            for col_name, data_type, fqcol in cols:
                hint = ""
                if fqcol in enum_hints:
                    vals = ", ".join(enum_hints[fqcol])
                    hint = f"  -- Values: {vals}"
                lines.append(f"  - {col_name} ({data_type}){hint}")
        return "\n".join(lines)

    schema_df = pd.DataFrame(rows)
    data_year_range = get_data_year_range(session)
    return _render(tables), _render(views), schema_df, known_identifiers, enum_hints, data_year_range


# ── SQL Validation ────────────────────────────────────────────────────────────

_DANGEROUS_KEYWORDS = re.compile(
    r'\b(DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE|GRANT|MERGE|CREATE|REVOKE|EXEC|EXECUTE)\b',
    re.IGNORECASE
)


def _strip_sql_comments(sql):
    """Remove SQL line comments and block comments."""
    sql = re.sub(r'--[^\n]*', '', sql)
    sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
    return sql.strip()


def _blank_string_literals(sql):
    """Replace the *contents* of single-quoted literals with empty strings.

    Keeps the quotes so statement structure is preserved, but prevents data from
    being mistaken for SQL. Without this, a legitimate filter such as
    WHERE RETURN_REASON = 'Needs update' trips the DDL/DML keyword guard.
    """
    return re.sub(r"'[^']*'", "''", sql)


def validate_sql(sql):
    """Check that SQL is a safe SELECT. Returns (is_valid, error_message)."""
    cleaned = _strip_sql_comments(sql)
    if not cleaned.upper().startswith('SELECT') and not cleaned.upper().startswith('WITH'):
        return False, "Generated SQL must be a SELECT or WITH statement."

    # Scan for keywords only outside string literals — literals are data, not SQL.
    scannable = _blank_string_literals(cleaned)

    # Reject stacked statements (e.g. "SELECT 1; DROP TABLE T"). A single
    # trailing semicolon is fine; anything after one is a second statement.
    if ';' in scannable.rstrip().rstrip(';'):
        return False, "Generated SQL must be a single statement."

    match = _DANGEROUS_KEYWORDS.search(scannable)
    if match:
        return False, f"Generated SQL contains forbidden keyword: {match.group(0).upper()}"
    return True, None


# A row cap only applies if LIMIT/FETCH is the *last* clause. A LIMIT inside a
# CTE or subquery caps that subquery, not the result set.
_TRAILING_ROW_CAP = re.compile(
    r'\b(?:LIMIT\s+\d+(?:\s+OFFSET\s+\d+)?'
    r'|FETCH\s+(?:FIRST|NEXT)\s+\d+\s+ROWS?\s+ONLY)\s*$',
    re.IGNORECASE
)


def ensure_limit(sql, max_rows=500):
    """Append LIMIT if the query does not already end with a row cap."""
    body = _strip_sql_comments(sql).rstrip().rstrip(';').rstrip()
    if _TRAILING_ROW_CAP.search(body):
        return sql
    return sql.rstrip().rstrip(';').rstrip() + f"\nLIMIT {max_rows}"


# ── SQL Generation (merged routing + generation) ──────────────────────────────

def sql_literal(value):
    """Escape a Python string for embedding in a Snowflake string literal.

    Doubling quotes alone is not enough: Snowflake also interprets backslash
    escapes inside string literals, so a value containing \\' would otherwise
    terminate the literal early. Backslashes must be escaped first.
    """
    return str(value).replace("\\", "\\\\").replace("'", "''")


def complete(session, prompt):
    """Send a prompt to Cortex COMPLETE and return the raw text response."""
    from prompts import CORTEX_MODEL

    raw = session.sql(
        f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{CORTEX_MODEL}', '{sql_literal(prompt)}') AS R"
    ).collect()[0]["R"]
    if not raw:
        raise ValueError("Cortex returned an empty response.")
    return raw.strip()


def _strip_markdown_fences(text):
    """Remove ```sql / ``` fences the model sometimes wraps its answer in."""
    return re.sub(r"```(?:sql|json)?", "", text).strip()


def parse_sql_response(raw, semantic_views):
    """Parse a {"sql": ..., "view": ...} response.

    Returns dict: {"sql": str, "view": str|None, "error": str|None}
    """
    raw = _strip_markdown_fences(raw)

    parsed = None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # The model may wrap the JSON in prose — pull out the first object.
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group())
            except json.JSONDecodeError:
                parsed = None

    if isinstance(parsed, dict) and parsed.get("sql"):
        view = parsed.get("view")
        if isinstance(view, str):
            view = view.strip()
            # Only trust a view name we actually publish.
            view = view if view in semantic_views else None
        else:
            view = None
        return {"sql": str(parsed["sql"]).strip(), "view": view, "error": None}

    # Fallback: the model returned bare SQL instead of JSON.
    if raw.upper().lstrip().startswith(("SELECT", "WITH")):
        return {"sql": raw, "view": None, "error": None}

    return {"sql": "", "view": None, "error": "Could not parse LLM response"}


def generate_sql(session, question, schema_context, semantic_views,
                 views_context="", history=None, corrections=None,
                 data_max_year=None):
    """Single LLM call producing SQL, optionally sourced from a semantic view.

    Returns dict: {"sql": str, "view": str|None, "error": str|None}
    """
    from prompts import build_router_and_sql_prompt

    prompt = build_router_and_sql_prompt(
        question, schema_context, views_context=views_context,
        history=history, corrections=corrections,
        data_max_year=data_max_year,
    )
    return parse_sql_response(complete(session, prompt), semantic_views)


def repair_sql(session, question, failed_sql, error_message, schema_context,
               semantic_views, views_context=""):
    """One repair attempt after Snowflake rejected the generated SQL.

    Returns the same shape as generate_sql.
    """
    from prompts import build_retry_prompt

    prompt = build_retry_prompt(
        question, failed_sql, error_message, schema_context, views_context=views_context
    )
    return parse_sql_response(complete(session, prompt), semantic_views)


# ── Schema Compliance (code-verified) ─────────────────────────────────────────

def _extract_identifiers_from_sql(sql):
    """Extract table/column-like identifiers from SQL for compliance checking."""
    cleaned = _strip_sql_comments(sql)
    # Remove string literals
    cleaned = re.sub(r"'[^']*'", '', cleaned)
    # Find dot-separated identifiers (e.g., SCHEMA.TABLE.COL or TABLE.COL)
    dot_ids = re.findall(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+', cleaned)
    # Find standalone identifiers (after FROM, JOIN, or as aliases)
    return [i.upper() for i in dot_ids]


def compute_schema_compliance(sql, known_identifiers):
    """Code-verified schema compliance: parse SQL identifiers and check each exists.
    
    Returns (score 1-10, reason string).
    """
    identifiers = _extract_identifiers_from_sql(sql)
    if not identifiers:
        return 10, "No table/column references to verify (code-verified)"

    valid = 0
    invalid = []
    for ident in identifiers:
        # Check if the full identifier or its parts are known
        parts = ident.split('.')
        found = False
        # Check the full identifier
        if ident in known_identifiers:
            found = True
        # Check table.column (last two parts)
        elif len(parts) >= 2 and f"{parts[-2]}.{parts[-1]}" in known_identifiers:
            found = True
        # Check just the last part (could be an alias)
        elif parts[-1] in known_identifiers:
            found = True
        if found:
            valid += 1
        else:
            # Could be an alias — don't penalize short single-segment names
            if len(parts) == 1:
                valid += 1  # likely an alias
            else:
                invalid.append(ident)

    total = len(identifiers)
    if total == 0:
        return 10, "No identifiers to check (code-verified)"
    ratio = valid / total
    score = max(1, min(10, round(ratio * 10)))
    if invalid:
        reason = f"{valid}/{total} identifiers verified; unrecognized: {', '.join(invalid[:3])} (code-verified)"
    else:
        reason = f"All {total} identifiers verified against live schema (code-verified)"
    return score, reason


# ── Confidence Scoring ────────────────────────────────────────────────────────

def score_sql(session, question, sql, known_identifiers):
    """Score SQL: RELEVANCE and SQL_QUALITY via LLM, SCHEMA_COMPLIANCE via code.
    Never raises — always returns a populated dict even if the LLM call fails.
    """
    from prompts import build_score_prompt

    # Code-verified schema compliance (never fails)
    compliance_score, compliance_reason = compute_schema_compliance(sql, known_identifiers)

    result = {
        "relevance": 0, "relevance_reason": "LLM scoring unavailable",
        "schema_compliance": compliance_score, "schema_compliance_reason": compliance_reason,
        "sql_quality": 0, "sql_quality_reason": "LLM scoring unavailable",
        "verdict": "NEEDS REVIEW", "raw": "",
        "llm_scored": False, "error": None,
    }

    # LLM-scored subjective criteria — safe, never raises
    try:
        raw = complete(session, build_score_prompt(question, sql))
        if raw:
            result["raw"] = raw
            result["llm_scored"] = True
            for line in raw.splitlines():
                line = line.strip()
                m = re.match(r"RELEVANCE:\s*(\d+)/10\s*\|\s*(.+)", line)
                if m:
                    result["relevance"] = int(m.group(1))
                    result["relevance_reason"] = m.group(2).strip()
                else:
                    m = re.match(r"SQL_QUALITY:\s*(\d+)/10\s*\|\s*(.+)", line)
                    if m:
                        result["sql_quality"] = int(m.group(1))
                        result["sql_quality_reason"] = m.group(2).strip()
                    else:
                        m = re.match(r"VERDICT:\s*(GOOD|NEEDS REVIEW|RISKY)", line)
                        if m:
                            result["verdict"] = m.group(1)
    except Exception as e:
        # Partial result already set above; schema compliance is still valid.
        # Record the cause so the sidebar can show why scoring degraded.
        result["error"] = f"score_sql: {e}"

    # Override verdict based on schema compliance
    if compliance_score < 5:
        result["verdict"] = "RISKY"
    elif compliance_score < 8 and result["verdict"] == "GOOD":
        result["verdict"] = "NEEDS REVIEW"

    # Mark if LLM scores couldn't be parsed
    if result["llm_scored"] and result["relevance"] == 0 and result["sql_quality"] == 0:
        result["verdict"] = "UNSCORED"
        result["relevance_reason"] = "Score parsing failed — see raw output"
        result["sql_quality_reason"] = "Score parsing failed — see raw output"

    return result


# ── Value Compliance (string literal validation) ──────────────────────────────

def _extract_string_literals(sql):
    """Extract all single-quoted string literals from SQL."""
    return re.findall(r"'([^']*)'", sql)


# Literals are only worth validating when they are compared against a column we
# have sampled values for. A literal in a THEN/AS/SELECT position is an output
# label (e.g. CASE ... THEN '0-30') and must never be flagged.
_EQUALITY_COMPARISON = re.compile(
    r"(?:\w+\.)?(\w+)\s*(?:=|!=|<>)\s*'([^']*)'", re.IGNORECASE
)
_IN_COMPARISON = re.compile(
    r"(?:\w+\.)?(\w+)\s+IN\s*\(([^)]*)\)", re.IGNORECASE
)


def check_value_compliance(sql, enum_hints):
    """Check literals compared against known enum columns.

    Only WHERE-style comparisons (col = 'x', col IN ('x','y')) are validated.
    Returns (score 1-10, reason, list_of_bad_values).
    """
    # Index sampled values by bare column name. The same column name can appear
    # in several tables (e.g. STATUS), so accept a value valid for any of them.
    values_by_column = {}
    for col_key, values in enum_hints.items():
        col_name = col_key.split('.')[-1].upper()
        bucket = values_by_column.setdefault(col_name, set())
        for v in values:
            bucket.add(v.upper())

    if not values_by_column:
        return 10, "No sampled enum values available to validate against", []

    cleaned = _strip_sql_comments(sql)

    # Collect (column, literal) pairs actually being compared.
    compared = []
    for col, lit in _EQUALITY_COMPARISON.findall(cleaned):
        compared.append((col.upper(), lit))
    for col, in_list in _IN_COMPARISON.findall(cleaned):
        for lit in _extract_string_literals(in_list):
            compared.append((col.upper(), lit))

    bad_values = []
    checked = 0
    for col, lit in compared:
        allowed = values_by_column.get(col)
        if not allowed:
            continue  # not a column we sampled — nothing to check against
        if '%' in lit or lit.strip() == '':
            continue  # LIKE-style pattern or empty
        checked += 1
        if lit.upper() not in allowed:
            bad_values.append(lit)

    if checked == 0:
        return 10, "No enum column comparisons to validate", []

    valid = checked - len(bad_values)
    score = max(1, min(10, round((valid / checked) * 10)))

    if bad_values:
        reason = f"{valid}/{checked} filter values valid; unrecognized: {', '.join(repr(v) for v in bad_values[:3])}"
    else:
        reason = f"All {checked} filter values match sampled column values"
    return score, reason, bad_values


# ── Query Corrections (learn from mistakes) ───────────────────────────────────

_CORRECTIONS_TABLE = "CONVERSATIONAL_BI.APP.QUERY_CORRECTIONS"


def _ensure_corrections_table(session):
    """Create the corrections table if it doesn't exist."""
    session.sql(f"""
        CREATE TABLE IF NOT EXISTS {_CORRECTIONS_TABLE} (
            CORRECTION_ID INT AUTOINCREMENT PRIMARY KEY,
            QUESTION VARCHAR(1000),
            BAD_SQL VARCHAR(5000),
            CORRECTED_SQL VARCHAR(5000),
            REASON VARCHAR(500),
            BAD_VALUES VARCHAR(500),
            CREATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
        )
    """).collect()


def save_correction(session, question, bad_sql, corrected_sql, reason="", bad_values=None):
    """Save a correction so the LLM can learn from past mistakes."""
    _ensure_corrections_table(session)
    q = sql_literal(question)
    bs = sql_literal(bad_sql)
    cs = sql_literal(corrected_sql)
    r = sql_literal(reason)
    bv = sql_literal(", ".join(bad_values) if bad_values else "")
    session.sql(f"""
        INSERT INTO {_CORRECTIONS_TABLE} (QUESTION, BAD_SQL, CORRECTED_SQL, REASON, BAD_VALUES)
        VALUES ('{q}', '{bs}', '{cs}', '{r}', '{bv}')
    """).collect()


def get_relevant_corrections(session, question, limit=3):
    """Fetch past corrections relevant to the current question."""
    _ensure_corrections_table(session)
    q = sql_literal(question)
    try:
        # NB: this WHERE must stay genuinely restrictive. An earlier version
        # ORed in `ARRAY_SIZE(SPLIT(q,' ')) > 0`, which is true for every
        # non-empty question — the filter was a no-op and the fallback below
        # was unreachable, so every question got the 3 newest corrections.
        rows = session.sql(f"""
            SELECT QUESTION, BAD_SQL, CORRECTED_SQL, REASON, BAD_VALUES
            FROM {_CORRECTIONS_TABLE}
            WHERE QUESTION ILIKE '%' || '{q}' || '%'
               OR '{q}' ILIKE '%' || QUESTION || '%'
            ORDER BY CREATED_AT DESC
            LIMIT {limit}
        """).collect()
        # No direct match — fall back to the most recent corrections
        if not rows:
            rows = session.sql(f"""
                SELECT QUESTION, BAD_SQL, CORRECTED_SQL, REASON, BAD_VALUES
                FROM {_CORRECTIONS_TABLE}
                ORDER BY CREATED_AT DESC
                LIMIT {limit}
            """).collect()
        return rows
    except Exception as e:
        logger.warning("correction lookup failed: %s", e)
        return []


# ── Query Execution ───────────────────────────────────────────────────────────

def run_query(session, sql):
    """Execute SQL and return (DataFrame, error_string)."""
    try:
        return pd.DataFrame(session.sql(sql).collect()), None
    except Exception as e:
        return None, str(e)


# ── SQL Formatting (display only) ────────────────────────────────────────────

_FORMAT_KEYWORDS = re.compile(
    r'\b(SELECT|FROM|WHERE|GROUP\s+BY|ORDER\s+BY|HAVING|LIMIT|OFFSET|'
    r'LEFT\s+JOIN|RIGHT\s+JOIN|FULL\s+JOIN|CROSS\s+JOIN|INNER\s+JOIN|JOIN|'
    r'ON|AND|OR|UNION\s+ALL|UNION|EXCEPT|INTERSECT|WITH|AS\s*\(|'
    r'CASE|WHEN|THEN|ELSE|END|FETCH\s+FIRST)\b',
    re.IGNORECASE,
)

_INDENT_KEYWORDS = {
    'SELECT', 'FROM', 'WHERE', 'GROUP BY', 'ORDER BY', 'HAVING',
    'LIMIT', 'OFFSET', 'UNION ALL', 'UNION', 'EXCEPT', 'INTERSECT',
    'FETCH FIRST', 'WITH',
}
_SUB_INDENT_KEYWORDS = {
    'LEFT JOIN', 'RIGHT JOIN', 'FULL JOIN', 'CROSS JOIN', 'INNER JOIN',
    'JOIN', 'ON', 'AND', 'OR', 'WHEN', 'THEN', 'ELSE', 'END',
}


def format_sql(sql):
    """Best-effort SQL formatting for display. Not used in execution."""
    if not sql:
        return sql
    # Normalise whitespace
    s = ' '.join(sql.split())
    parts = _FORMAT_KEYWORDS.split(s)
    lines = []
    for part in parts:
        token = part.strip()
        if not token:
            continue
        upper = ' '.join(token.upper().split())
        if upper in _INDENT_KEYWORDS:
            lines.append(token.upper())
        elif upper in _SUB_INDENT_KEYWORDS:
            lines.append('  ' + token.upper())
        else:
            if lines:
                lines[-1] += ' ' + token
            else:
                lines.append(token)
    return '\n'.join(lines)
