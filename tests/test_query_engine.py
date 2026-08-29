"""Offline tests for query_engine's pure functions.

These never open a Snowflake session and never call Cortex, so they cost
nothing to run and are safe in CI. Run with:

    python -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from prompts import SEMANTIC_VIEWS  # noqa: E402
from query_engine import (  # noqa: E402
    validate_sql,
    ensure_limit,
    check_value_compliance,
    compute_schema_compliance,
    parse_sql_response,
    sql_literal,
    _blank_string_literals,
)


class TestSqlLiteral(unittest.TestCase):
    def test_doubles_single_quotes(self):
        self.assertEqual(sql_literal("it's"), "it''s")

    def test_escapes_backslashes_before_quotes(self):
        # Snowflake honours backslash escapes inside string literals, so a
        # trailing backslash would otherwise escape the doubled quote and
        # let the value break out of the literal.
        self.assertEqual(sql_literal("a\\'b"), "a\\\\''b")

    def test_lone_backslash_is_doubled(self):
        self.assertEqual(sql_literal("C:\\path"), "C:\\\\path")

    def test_plain_text_unchanged(self):
        self.assertEqual(sql_literal("revenue by region"), "revenue by region")

    def test_accepts_non_string(self):
        self.assertEqual(sql_literal(42), "42")


class TestValidateSql(unittest.TestCase):
    def test_accepts_plain_select(self):
        self.assertEqual(validate_sql("SELECT A FROM T"), (True, None))

    def test_accepts_cte(self):
        self.assertEqual(validate_sql("WITH x AS (SELECT 1) SELECT * FROM x"), (True, None))

    def test_rejects_non_select(self):
        ok, err = validate_sql("SHOW TABLES")
        self.assertFalse(ok)

    def test_blocks_real_ddl(self):
        for sql in [
            "SELECT 1; DROP TABLE CUSTOMERS",
            "SELECT * FROM T; DELETE FROM T",
            "WITH x AS (SELECT 1) SELECT * FROM x; TRUNCATE TABLE T",
        ]:
            ok, err = validate_sql(sql)
            self.assertFalse(ok, f"should have blocked: {sql}")

    def test_blocks_keyword_hidden_in_comment(self):
        # Comments are stripped, so a keyword there is neutralised, but the
        # statement must still be a legitimate SELECT.
        ok, _ = validate_sql("SELECT A FROM T -- DROP TABLE T")
        self.assertTrue(ok)

    # --- Regression: literals are data, not SQL -----------------------------
    # Previously validate_sql scanned the raw string, so a legitimate filter
    # whose value contained "update"/"create" was rejected outright.

    def test_allows_dml_keyword_inside_string_literal(self):
        cases = [
            "SELECT * FROM RETURNS WHERE RETURN_REASON = 'Needs update'",
            "SELECT NAME FROM CUSTOMERS WHERE SEGMENT = 'Enterprise Create'",
            "SELECT * FROM JOB_HISTORY WHERE CHANGE_TYPE = 'Insert transfer'",
            "SELECT CASE WHEN X > 0 THEN 'Merge candidate' ELSE 'None' END FROM T",
        ]
        for sql in cases:
            ok, err = validate_sql(sql)
            self.assertTrue(ok, f"should have allowed: {sql} (got {err})")

    def test_still_blocks_keyword_outside_literal_alongside_one_inside(self):
        ok, _ = validate_sql("SELECT 'safe update' FROM T; DROP TABLE T")
        self.assertFalse(ok)

    def test_blank_string_literals_preserves_structure(self):
        self.assertEqual(
            _blank_string_literals("WHERE A = 'x' AND B = 'y'"),
            "WHERE A = '' AND B = ''",
        )


class TestEnsureLimit(unittest.TestCase):
    def test_appends_when_missing(self):
        self.assertIn("LIMIT 500", ensure_limit("SELECT A FROM T"))

    def test_preserves_trailing_limit(self):
        sql = "SELECT A FROM T ORDER BY A DESC LIMIT 5"
        self.assertEqual(ensure_limit(sql), sql)

    def test_preserves_trailing_limit_offset(self):
        sql = "SELECT A FROM T LIMIT 10 OFFSET 20"
        self.assertEqual(ensure_limit(sql), sql)

    def test_preserves_fetch_first(self):
        sql = "SELECT A FROM T FETCH FIRST 10 ROWS ONLY"
        self.assertEqual(ensure_limit(sql), sql)

    def test_strips_trailing_semicolon_before_appending(self):
        out = ensure_limit("SELECT A FROM T;")
        self.assertIn("LIMIT 500", out)
        self.assertNotIn(";", out)

    def test_trailing_comment_does_not_swallow_limit(self):
        out = ensure_limit("SELECT A FROM T -- note")
        self.assertTrue(out.rstrip().endswith("LIMIT 500"))
        self.assertIn("\n", out)

    # --- Regression: inner LIMIT must not suppress the outer row cap --------
    # Previously any LIMIT anywhere (including inside a CTE) skipped the cap,
    # so these queries could return an unbounded result set.

    def test_inner_cte_limit_still_gets_outer_cap(self):
        sql = ("WITH top10 AS (SELECT PRODUCT_ID FROM PRODUCTS ORDER BY REV DESC LIMIT 10) "
               "SELECT o.* FROM ORDERS o JOIN top10 t ON o.PRODUCT_ID = t.PRODUCT_ID")
        self.assertTrue(ensure_limit(sql).rstrip().endswith("LIMIT 500"))

    def test_subquery_limit_still_gets_outer_cap(self):
        sql = "SELECT * FROM ORDERS WHERE ID IN (SELECT ID FROM T LIMIT 3)"
        self.assertTrue(ensure_limit(sql).rstrip().endswith("LIMIT 500"))


class TestCheckValueCompliance(unittest.TestCase):
    ENUM_HINTS = {
        "SALES.ORDERS.STATUS": ["Completed", "Cancelled", "Pending"],
        "SALES.PRODUCTS.CATEGORY": ["Electronics", "Apparel"],
        "FINANCE.INVOICES.INVOICE_STATUS": ["Paid", "Unpaid", "Overdue"],
    }

    def test_valid_filter_value_passes(self):
        score, _, bad = check_value_compliance(
            "SELECT * FROM ORDERS WHERE STATUS = 'Completed'", self.ENUM_HINTS)
        self.assertEqual((score, bad), (10, []))

    def test_invalid_filter_value_flagged(self):
        score, _, bad = check_value_compliance(
            "SELECT * FROM ORDERS WHERE STATUS = 'Shipped'", self.ENUM_HINTS)
        self.assertEqual(bad, ["Shipped"])
        self.assertLess(score, 10)

    def test_qualified_column_reference(self):
        _, _, bad = check_value_compliance(
            "SELECT * FROM ORDERS o WHERE o.STATUS = 'Nope'", self.ENUM_HINTS)
        self.assertEqual(bad, ["Nope"])

    def test_in_list_values_checked(self):
        _, _, bad = check_value_compliance(
            "SELECT * FROM ORDERS WHERE STATUS IN ('Completed', 'Bogus')", self.ENUM_HINTS)
        self.assertEqual(bad, ["Bogus"])

    def test_unknown_column_is_not_checked(self):
        score, _, bad = check_value_compliance(
            "SELECT * FROM T WHERE SOME_FREE_TEXT = 'anything at all'", self.ENUM_HINTS)
        self.assertEqual((score, bad), (10, []))

    def test_like_pattern_skipped(self):
        score, _, bad = check_value_compliance(
            "SELECT * FROM ORDERS WHERE STATUS LIKE '%Complete%'", self.ENUM_HINTS)
        self.assertEqual((score, bad), (10, []))

    # --- Regression: output labels are not filter values --------------------
    # Sample question 91 ("invoice amount by aging bucket") produced CASE
    # labels that were previously reported as suspicious values, forcing a
    # spurious RISKY verdict on a perfectly good query.

    def test_case_labels_are_not_flagged(self):
        sql = ("SELECT CASE WHEN DAYS <= 30 THEN '0-30' "
               "WHEN DAYS <= 60 THEN '31-60' "
               "WHEN DAYS <= 90 THEN '61-90' ELSE '90+' END AS BUCKET, "
               "SUM(AMOUNT) FROM INVOICES WHERE INVOICE_STATUS = 'Unpaid' GROUP BY 1")
        score, _, bad = check_value_compliance(sql, self.ENUM_HINTS)
        self.assertEqual(bad, [])
        self.assertEqual(score, 10)

    def test_column_alias_label_not_flagged(self):
        sql = "SELECT 'Q1' AS QUARTER, SUM(X) FROM T"
        score, _, bad = check_value_compliance(sql, self.ENUM_HINTS)
        self.assertEqual((score, bad), (10, []))


class TestComputeSchemaCompliance(unittest.TestCase):
    KNOWN = {"SALES.ORDERS.STATUS", "ORDERS.STATUS", "ORDERS", "SALES.ORDERS", "STATUS"}

    def test_known_identifiers_score_high(self):
        score, _ = compute_schema_compliance("SELECT ORDERS.STATUS FROM SALES.ORDERS", self.KNOWN)
        self.assertEqual(score, 10)

    def test_unknown_identifier_lowers_score(self):
        score, reason = compute_schema_compliance(
            "SELECT MADEUP.COLUMN FROM NOWHERE.TABLE", self.KNOWN)
        self.assertLess(score, 10)

    def test_no_identifiers_scores_ten(self):
        score, _ = compute_schema_compliance("SELECT 1", self.KNOWN)
        self.assertEqual(score, 10)


class TestParseSqlResponse(unittest.TestCase):
    VIEW = "CONVERSATIONAL_BI.SALES.V_MONTHLY_REVENUE"

    def test_parses_plain_json(self):
        out = parse_sql_response('{"sql": "SELECT 1", "view": null}', SEMANTIC_VIEWS)
        self.assertEqual((out["sql"], out["view"], out["error"]), ("SELECT 1", None, None))

    def test_parses_known_view(self):
        raw = '{"sql": "SELECT * FROM V", "view": "%s"}' % self.VIEW
        self.assertEqual(parse_sql_response(raw, SEMANTIC_VIEWS)["view"], self.VIEW)

    def test_rejects_unknown_view_but_keeps_sql(self):
        raw = '{"sql": "SELECT 1", "view": "SOME.MADE.UP_VIEW"}'
        out = parse_sql_response(raw, SEMANTIC_VIEWS)
        self.assertIsNone(out["view"])
        self.assertEqual(out["sql"], "SELECT 1")

    def test_strips_markdown_fences(self):
        raw = '```json\n{"sql": "SELECT 1", "view": null}\n```'
        self.assertEqual(parse_sql_response(raw, SEMANTIC_VIEWS)["sql"], "SELECT 1")

    def test_extracts_json_wrapped_in_prose(self):
        raw = 'Here you go:\n{"sql": "SELECT 1", "view": null}\nHope that helps.'
        self.assertEqual(parse_sql_response(raw, SEMANTIC_VIEWS)["sql"], "SELECT 1")

    def test_falls_back_to_bare_sql(self):
        out = parse_sql_response("SELECT A FROM T", SEMANTIC_VIEWS)
        self.assertEqual((out["sql"], out["error"]), ("SELECT A FROM T", None))

    def test_reports_error_when_unparseable(self):
        out = parse_sql_response("I cannot answer that question.", SEMANTIC_VIEWS)
        self.assertEqual(out["sql"], "")
        self.assertIsNotNone(out["error"])

    def test_handles_sql_containing_braces(self):
        raw = '{"sql": "SELECT REGEXP_SUBSTR(A, \'x{2}\') FROM T", "view": null}'
        self.assertIn("REGEXP_SUBSTR", parse_sql_response(raw, SEMANTIC_VIEWS)["sql"])


if __name__ == "__main__":
    unittest.main()
