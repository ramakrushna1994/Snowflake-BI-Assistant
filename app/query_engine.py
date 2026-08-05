"""Query engine: schema fetch, SQL generation, validation, scoring, execution (v2.2)."""

import re
import json
import pandas as pd


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
            values = [r[column] for r in rows]
            if values:
                enum_hints[f"{schema}.{table}.{column}"] = values
        except Exception:
            pass
    return enum_hints


def get_live_schema(session):
    """Fetch schema metadata once. Returns (schema_text, schema_df, table_columns_set, enum_hints).
    
    table_columns_set is a set of uppercase "SCHEMA.TABLE.COLUMN" for compliance checking.
    enum_hints is a dict mapping "SCHEMA.TABLE.COLUMN" to list of valid values.
    """
    rows = session.sql("""
        SELECT c.TABLE_SCHEMA, c.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE
        FROM CONVERSATIONAL_BI.INFORMATION_SCHEMA.COLUMNS c
        JOIN CONVERSATIONAL_BI.INFORMATION_SCHEMA.TABLES t
          ON c.TABLE_SCHEMA = t.TABLE_SCHEMA AND c.TABLE_NAME = t.TABLE_NAME
        WHERE c.TABLE_SCHEMA IN ('SALES','HR','FINANCE')
          AND t.TABLE_TYPE = 'BASE TABLE'
        ORDER BY c.TABLE_SCHEMA, c.TABLE_NAME, c.ORDINAL_POSITION
    """).collect()

    tables = {}
    known_identifiers = set()
    for r in rows:
        schema = r['TABLE_SCHEMA']
        table = r['TABLE_NAME']
        column = r['COLUMN_NAME']
        fqn = f"CONVERSATIONAL_BI.{schema}.{table}"
        tables.setdefault(fqn, []).append((column, r['DATA_TYPE'], f"{schema}.{table}.{column}"))
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

    # Build schema text with enum annotations
    lines = []
    for tbl, cols in tables.items():
        lines.append(tbl)
        for col_name, data_type, fqcol in cols:
            hint = ""
            if fqcol in enum_hints:
                vals = ", ".join(enum_hints[fqcol])
                hint = f"  -- Values: {vals}"
            lines.append(f"  - {col_name} ({data_type}){hint}")
    schema_text = "\n".join(lines)
    schema_df = pd.DataFrame(rows)
    return schema_text, schema_df, known_identifiers, enum_hints


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


def validate_sql(sql):
    """Check that SQL is a safe SELECT. Returns (is_valid, error_message)."""
    cleaned = _strip_sql_comments(sql)
    if not cleaned.upper().startswith('SELECT') and not cleaned.upper().startswith('WITH'):
        return False, "Generated SQL must be a SELECT or WITH statement."
    if _DANGEROUS_KEYWORDS.search(cleaned):
        match = _DANGEROUS_KEYWORDS.search(cleaned)
        return False, f"Generated SQL contains forbidden keyword: {match.group(0).upper()}"
    return True, None


def ensure_limit(sql, max_rows=500):
    """Append LIMIT 500 if no LIMIT clause exists."""
    if not re.search(r'\bLIMIT\b', sql, re.IGNORECASE):
        sql = sql.rstrip().rstrip(';')
        sql += f"\nLIMIT {max_rows}"
    return sql


# ── SQL Generation (merged routing + generation) ──────────────────────────────

def generate_sql(session, question, schema_context, semantic_views, history=None, corrections=None):
    """Single LLM call: routes to semantic view or generates SQL.
    
    Returns dict: {"type": "view"|"sql", "value": str, "confidence": str|None, "error": str|None}
    """
    from prompts import build_router_and_sql_prompt, CORTEX_MODEL

    prompt = build_router_and_sql_prompt(question, schema_context, history=history, corrections=corrections)
    prompt_escaped = prompt.replace("'", "''")
    raw = session.sql(
        f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{CORTEX_MODEL}', '{prompt_escaped}') AS R"
    ).collect()[0]["R"]
    if not raw:
        raise ValueError("Cortex returned an empty response.")
    raw = raw.strip()

    # Try to parse JSON response
    try:
        # Extract JSON from response (model might wrap it in text)
        json_match = re.search(r'\{[^{}]*\}', raw)
        if json_match:
            parsed = json.loads(json_match.group())
        else:
            parsed = json.loads(raw)

        if "view" in parsed:
            view_name = parsed["view"].strip()
            confidence = parsed.get("confidence", "LOW").upper()
            # Exact match: view must exist in registry
            if view_name in semantic_views:
                if confidence == "HIGH":
                    return {"type": "view", "value": view_name, "confidence": "HIGH", "error": None}
                else:
                    # LOW confidence — fall through to use SQL if available
                    pass
        if "sql" in parsed:
            return {"type": "sql", "value": parsed["sql"].strip(), "confidence": None, "error": None}
    except (json.JSONDecodeError, KeyError):
        pass

    # Fallback: if response looks like raw SQL (no JSON), use it directly
    if raw.upper().lstrip().startswith(("SELECT", "WITH")):
        return {"type": "sql", "value": raw, "confidence": None, "error": None}

    # Fallback: parse plain-text view response (e.g. "VIEW_NAME | HIGH" or "VIEW_NAME\nCONFIDENCE: HIGH")
    lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]
    if lines:
        view_candidate = lines[0].split("|")[0].strip()
        confidence = "HIGH"
        for line in lines:
            if "LOW" in line.upper():
                confidence = "LOW"
        if view_candidate in semantic_views and confidence == "HIGH":
            return {"type": "view", "value": view_candidate, "confidence": "HIGH", "error": None}

    return {"type": "sql", "value": raw, "confidence": None, "error": "Could not parse LLM response"}


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
    from prompts import build_score_prompt, CORTEX_MODEL

    # Code-verified schema compliance (never fails)
    compliance_score, compliance_reason = compute_schema_compliance(sql, known_identifiers)

    result = {
        "relevance": 0, "relevance_reason": "LLM scoring unavailable",
        "schema_compliance": compliance_score, "schema_compliance_reason": compliance_reason,
        "sql_quality": 0, "sql_quality_reason": "LLM scoring unavailable",
        "verdict": "NEEDS REVIEW", "raw": "",
        "llm_scored": False,
    }

    # LLM-scored subjective criteria — safe, never raises
    try:
        prompt = build_score_prompt(question, sql)
        prompt_escaped = prompt.replace("'", "''")
        raw = session.sql(
            f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{CORTEX_MODEL}', '{prompt_escaped}') AS R"
        ).collect()[0]["R"]
        if raw:
            raw = raw.strip()
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
    except Exception:
        pass  # partial result already set above; schema compliance still valid

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


def check_value_compliance(sql, enum_hints):
    """Check string literals in SQL against known enum values.
    
    Returns (score 1-10, reason, list_of_bad_values).
    """
    literals = _extract_string_literals(sql)
    if not literals:
        return 10, "No string literals to validate", []

    # Build a reverse lookup: value -> which columns accept it
    value_to_columns = {}
    all_known_values = set()
    for col_key, values in enum_hints.items():
        for v in values:
            all_known_values.add(v.upper())
            value_to_columns.setdefault(v.upper(), []).append(col_key)

    # Check each literal
    bad_values = []
    checked = 0
    for lit in literals:
        # Skip date-like strings, numbers, wildcards
        if re.match(r'^\d{4}[-/]\d{2}', lit):
            continue
        if re.match(r'^[\d.]+$', lit):
            continue
        if '%' in lit:
            continue
        # Only check if it looks like an enum value (short alpha string)
        if len(lit) > 50 or lit.strip() == '':
            continue
        checked += 1
        if lit.upper() not in all_known_values:
            bad_values.append(lit)

    if checked == 0:
        return 10, "No enum-like literals to validate", []

    valid = checked - len(bad_values)
    ratio = valid / checked
    score = max(1, min(10, round(ratio * 10)))

    if bad_values:
        reason = f"{valid}/{checked} literals valid; unrecognized: {', '.join(repr(v) for v in bad_values[:3])}"
    else:
        reason = f"All {checked} string literals match known enum values"
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
    q = question.replace("'", "''")
    bs = bad_sql.replace("'", "''")
    cs = corrected_sql.replace("'", "''")
    r = reason.replace("'", "''")
    bv = ", ".join(bad_values) if bad_values else ""
    bv = bv.replace("'", "''")
    session.sql(f"""
        INSERT INTO {_CORRECTIONS_TABLE} (QUESTION, BAD_SQL, CORRECTED_SQL, REASON, BAD_VALUES)
        VALUES ('{q}', '{bs}', '{cs}', '{r}', '{bv}')
    """).collect()


def get_relevant_corrections(session, question, limit=3):
    """Fetch past corrections relevant to the current question."""
    _ensure_corrections_table(session)
    q = question.replace("'", "''")
    try:
        rows = session.sql(f"""
            SELECT QUESTION, BAD_SQL, CORRECTED_SQL, REASON, BAD_VALUES
            FROM {_CORRECTIONS_TABLE}
            WHERE QUESTION ILIKE '%' || '{q}' || '%'
               OR '{q}' ILIKE '%' || QUESTION || '%'
               OR ARRAY_SIZE(SPLIT('{q}', ' ')) > 0
            ORDER BY CREATED_AT DESC
            LIMIT {limit}
        """).collect()
        # If broad match returns nothing useful, get most recent corrections
        if not rows:
            rows = session.sql(f"""
                SELECT QUESTION, BAD_SQL, CORRECTED_SQL, REASON, BAD_VALUES
                FROM {_CORRECTIONS_TABLE}
                ORDER BY CREATED_AT DESC
                LIMIT {limit}
            """).collect()
        return rows
    except Exception:
        return []


# ── Query Execution ───────────────────────────────────────────────────────────

def run_query(session, sql):
    """Execute SQL and return (DataFrame, error_string)."""
    try:
        return pd.DataFrame(session.sql(sql).collect()), None
    except Exception as e:
        return None, str(e)
