"""Query engine: schema fetch, SQL generation, validation, scoring, execution (v2.1)."""

import re
import json
import pandas as pd


def get_live_schema(session):
    """Fetch schema metadata once. Returns (schema_text, schema_df, table_columns_set).
    
    table_columns_set is a set of uppercase "SCHEMA.TABLE.COLUMN" for compliance checking.
    """
    rows = session.sql("""
        SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE
        FROM CONVERSATIONAL_BI.INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA IN ('SALES','HR','FINANCE')
        ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION
    """).collect()

    tables = {}
    known_identifiers = set()
    for r in rows:
        schema = r['TABLE_SCHEMA']
        table = r['TABLE_NAME']
        column = r['COLUMN_NAME']
        fqn = f"CONVERSATIONAL_BI.{schema}.{table}"
        tables.setdefault(fqn, []).append(f"  - {column} ({r['DATA_TYPE']})")
        # Track identifiers for compliance checking
        known_identifiers.add(f"{schema}.{table}.{column}".upper())
        known_identifiers.add(f"CONVERSATIONAL_BI.{schema}.{table}.{column}".upper())
        known_identifiers.add(f"{table}.{column}".upper())
        known_identifiers.add(table.upper())
        known_identifiers.add(f"{schema}.{table}".upper())
        known_identifiers.add(f"CONVERSATIONAL_BI.{schema}.{table}".upper())
        known_identifiers.add(column.upper())

    lines = []
    for tbl, cols in tables.items():
        lines.append(tbl)
        lines.extend(cols)
    schema_text = "\n".join(lines)
    schema_df = pd.DataFrame(rows)
    return schema_text, schema_df, known_identifiers


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

def generate_sql(session, question, schema_context, semantic_views):
    """Single LLM call: routes to semantic view or generates SQL.
    
    Returns dict: {"type": "view"|"sql", "value": str, "confidence": str|None, "error": str|None}
    """
    from prompts import build_router_and_sql_prompt, CORTEX_MODEL

    prompt = build_router_and_sql_prompt(question, schema_context)
    prompt_escaped = prompt.replace("'", "''")
    raw = session.sql(
        f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{CORTEX_MODEL}', '{prompt_escaped}') AS R"
    ).collect()[0]["R"].strip()

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

def _trim_schema_for_sql(sql, schema_context):
    """Extract only the table definitions referenced in the SQL from full schema_context."""
    # Find table names referenced in SQL (dot-separated identifiers with 2-3 parts)
    sql_upper = sql.upper()
    lines = schema_context.split("\n")
    trimmed = []
    include_table = False
    for line in lines:
        if not line.startswith("  "):
            # This is a table header line (e.g. CONVERSATIONAL_BI.SALES.PRODUCTS)
            include_table = line.strip().upper() in sql_upper or \
                            line.strip().split(".")[-1] in sql_upper
            if include_table:
                trimmed.append(line)
        elif include_table:
            trimmed.append(line)
    return "\n".join(trimmed) if trimmed else schema_context


def score_sql(session, question, sql, schema_context, known_identifiers):
    """Score SQL: RELEVANCE and SQL_QUALITY via LLM, SCHEMA_COMPLIANCE via code."""
    from prompts import build_score_prompt, CORTEX_MODEL

    # Code-verified schema compliance
    compliance_score, compliance_reason = compute_schema_compliance(sql, known_identifiers)

    # Trim schema to only tables referenced in the SQL (reduces token usage)
    relevant_schema = _trim_schema_for_sql(sql, schema_context)

    # LLM-scored subjective criteria
    prompt = build_score_prompt(question, sql)
    prompt_escaped = prompt.replace("'", "''")
    raw = session.sql(
        f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{CORTEX_MODEL}', '{prompt_escaped}') AS R"
    ).collect()[0]["R"].strip()

    result = {
        "relevance": 0, "relevance_reason": "",
        "schema_compliance": compliance_score, "schema_compliance_reason": compliance_reason,
        "sql_quality": 0, "sql_quality_reason": "",
        "verdict": "NEEDS REVIEW", "raw": raw
    }

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

    # Override verdict if schema compliance is low
    if compliance_score < 5:
        result["verdict"] = "RISKY"
    elif compliance_score < 8 and result["verdict"] == "GOOD":
        result["verdict"] = "NEEDS REVIEW"

    return result


# ── Query Execution ───────────────────────────────────────────────────────────

def run_query(session, sql):
    """Execute SQL and return (DataFrame, error_string)."""
    try:
        return pd.DataFrame(session.sql(sql).collect()), None
    except Exception as e:
        return None, str(e)
