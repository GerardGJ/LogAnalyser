import src.agents.synthesizer_agent as synthesizer_agent
from src.agents.synthesizer_agent import synthesize_response


class FakeModel:
    """A stand-in for the model `get_agent_model("synthesizer_agent")` would
    return, so combined-route tests stay deterministic without a live LLM."""

    def __init__(self, response):
        self.response = response
        self.invocations = []

    def invoke(self, prompt):
        self.invocations.append(prompt)
        if isinstance(self.response, Exception):
            raise self.response

        class Resp:
            content = self.response

        return Resp()


def _explode_if_called(*args, **kwargs):
    raise AssertionError("get_agent_model() should not be called for a single-route response")


class TestSqlOnlyResult:
    def test_includes_query_results_section(self, monkeypatch):
        monkeypatch.setattr(synthesizer_agent, "get_agent_model", _explode_if_called)

        result = synthesize_response("how many errors today?", sql_result="3 errors found")

        assert "## Query Results" in result
        assert "3 errors found" in result
        assert "## Root Cause Analysis" not in result


class TestDiagnosticOnlyResult:
    def test_includes_root_cause_section(self, monkeypatch):
        monkeypatch.setattr(synthesizer_agent, "get_agent_model", _explode_if_called)

        result = synthesize_response(
            "why did it fail?", diagnostic_result="**Primary Issue**: DB timeout"
        )

        assert "## Root Cause Analysis" in result
        assert "DB timeout" in result
        assert "## Query Results" not in result


class TestCombinedResultsUsesLlmSynthesis:
    def test_calls_model_and_returns_its_narrative(self, monkeypatch):
        fake_model = FakeModel("The connection pool was exhausted, causing 12 errors in sleep_app.")
        monkeypatch.setattr(synthesizer_agent, "get_agent_model", lambda name: fake_model)

        result = synthesize_response(
            "why so many errors, show top apps",
            sql_result="sleep_app: 12 errors",
            diagnostic_result="**Primary Issue**: connection pool exhausted",
        )

        assert result == "The connection pool was exhausted, causing 12 errors in sleep_app."
        assert len(fake_model.invocations) == 1

    def test_prompt_includes_question_and_both_results(self, monkeypatch):
        fake_model = FakeModel("merged answer")
        monkeypatch.setattr(synthesizer_agent, "get_agent_model", lambda name: fake_model)

        synthesize_response(
            "why so many errors, show top apps",
            sql_result="sleep_app: 12 errors",
            diagnostic_result="**Primary Issue**: connection pool exhausted",
        )

        prompt = fake_model.invocations[0]
        assert "why so many errors, show top apps" in prompt
        assert "sleep_app: 12 errors" in prompt
        assert "connection pool exhausted" in prompt

    def test_prompt_includes_warnings_when_present(self, monkeypatch):
        fake_model = FakeModel("merged answer")
        monkeypatch.setattr(synthesizer_agent, "get_agent_model", lambda name: fake_model)

        synthesize_response(
            "why so many errors, show top apps",
            sql_result="sleep_app: 12 errors",
            diagnostic_result="**Primary Issue**: connection pool exhausted",
            errors=["Query retried once"],
        )

        assert "Query retried once" in fake_model.invocations[0]

    def test_falls_back_to_template_when_llm_call_fails(self, monkeypatch):
        fake_model = FakeModel(RuntimeError("model unavailable"))
        monkeypatch.setattr(synthesizer_agent, "get_agent_model", lambda name: fake_model)

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

    def test_llm_output_is_still_pii_scrubbed(self, monkeypatch):
        fake_model = FakeModel("Contact admin@example.com about the 12 errors in sleep_app.")
        monkeypatch.setattr(synthesizer_agent, "get_agent_model", lambda name: fake_model)

        result = synthesize_response(
            "why so many errors, show top apps",
            sql_result="sleep_app: 12 errors",
            diagnostic_result="**Primary Issue**: connection pool exhausted",
        )

        assert "admin@example.com" not in result
        assert "[REDACTED_EMAIL]" in result


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
