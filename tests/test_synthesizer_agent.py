from src.agents.synthesizer_agent import synthesize_response


class TestSqlOnlyResult:
    def test_includes_query_results_section(self):
        result = synthesize_response("how many errors today?", sql_result="3 errors found")

        assert "## Query Results" in result
        assert "3 errors found" in result
        assert "## Root Cause Analysis" not in result


class TestDiagnosticOnlyResult:
    def test_includes_root_cause_section(self):
        result = synthesize_response(
            "why did it fail?", diagnostic_result="**Primary Issue**: DB timeout"
        )

        assert "## Root Cause Analysis" in result
        assert "DB timeout" in result
        assert "## Query Results" not in result


class TestCombinedResults:
    def test_both_sections_present_in_diagnostic_before_sql_order(self):
        result = synthesize_response(
            "why so many errors, show top apps",
            sql_result="sleep_app: 12 errors",
            diagnostic_result="**Primary Issue**: connection pool exhausted",
        )

        assert "## Root Cause Analysis" in result
        assert "## Query Results" in result
        assert result.index("## Root Cause Analysis") < result.index("## Query Results")
        assert "connection pool exhausted" in result
        assert "sleep_app: 12 errors" in result


class TestEmptyResultsFallback:
    def test_no_results_message_when_both_are_none(self):
        result = synthesize_response("what is the weather today?")
        assert "No results available" in result

    def test_no_results_message_when_both_are_empty_strings(self):
        result = synthesize_response("unsupported question", sql_result="", diagnostic_result="")
        assert "No results available" in result


class TestWarningsSection:
    def test_warnings_included_when_present(self):
        result = synthesize_response(
            "count errors",
            sql_result="5 errors",
            errors=["Query retried once due to a transient timeout"],
        )
        assert "## Warnings" in result
        assert "Query retried once due to a transient timeout" in result

    def test_no_warnings_section_when_errors_is_none(self):
        result = synthesize_response("count errors", sql_result="5 errors")
        assert "## Warnings" not in result

    def test_no_warnings_section_when_errors_is_empty_list(self):
        result = synthesize_response("count errors", sql_result="5 errors", errors=[])
        assert "## Warnings" not in result

    def test_multiple_warnings_each_rendered_as_bullet(self):
        result = synthesize_response(
            "count errors",
            sql_result="5 errors",
            errors=["first warning", "second warning"],
        )
        assert "- first warning" in result
        assert "- second warning" in result


class TestPiiScrubbing:
    def test_scrubs_pii_from_sql_result(self):
        result = synthesize_response(
            "who reported this?", sql_result="reported by admin@example.com"
        )
        assert "admin@example.com" not in result
        assert "[REDACTED_EMAIL]" in result

    def test_scrubs_pii_from_diagnostic_result(self):
        result = synthesize_response(
            "why did it fail?", diagnostic_result="contact admin@example.com from 10.0.0.5"
        )
        assert "admin@example.com" not in result
        assert "10.0.0.5" not in result
        assert "[REDACTED_EMAIL]" in result
        assert "[REDACTED_IP]" in result

    def test_scrubs_pii_from_question_heading(self):
        result = synthesize_response("who is admin@example.com?", sql_result="no match")
        assert "admin@example.com" not in result
        assert "[REDACTED_EMAIL]" in result


class TestQuestionHeading:
    def test_empty_question_falls_back_to_generic_heading(self):
        result = synthesize_response("", sql_result="5 errors")
        assert result.startswith("# Question")

    def test_whitespace_only_question_falls_back_to_generic_heading(self):
        result = synthesize_response("   ", sql_result="5 errors")
        assert result.startswith("# Question")
