import src.agents.diagnostic_agent as diagnostic_agent


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeAgent:
    def __init__(self, response):
        self.response = response
        self.invocations = []

    def invoke(self, payload):
        self.invocations.append(payload)
        if isinstance(self.response, Exception):
            raise self.response
        return {"messages": [FakeMessage(self.response)]}


class TestDiagnoseLogFailure:
    def test_returns_final_analysis_message(self, monkeypatch):
        fake_agent = FakeAgent("**Primary Issue**: Database connection lost")
        monkeypatch.setattr(diagnostic_agent, "get_diagnostic_agent", lambda: fake_agent)

        result = diagnostic_agent.diagnose_log_failure("ERROR: db connection lost")

        assert result == "**Primary Issue**: Database connection lost"
        assert len(fake_agent.invocations) == 1

    def test_scrubs_pii_from_input_log_payload(self, monkeypatch):
        fake_agent = FakeAgent("ok")
        monkeypatch.setattr(diagnostic_agent, "get_diagnostic_agent", lambda: fake_agent)

        diagnostic_agent.diagnose_log_failure("failure reported by admin@example.com from 10.0.0.5")

        sent_prompt = fake_agent.invocations[0]["messages"][0][1]
        assert "admin@example.com" not in sent_prompt
        assert "10.0.0.5" not in sent_prompt
        assert "[REDACTED_EMAIL]" in sent_prompt
        assert "[REDACTED_IP]" in sent_prompt

    def test_scrubs_pii_from_output_analysis(self, monkeypatch):
        fake_agent = FakeAgent("Contact admin@example.com to rotate the credential")
        monkeypatch.setattr(diagnostic_agent, "get_diagnostic_agent", lambda: fake_agent)

        result = diagnostic_agent.diagnose_log_failure("some failure")

        assert "admin@example.com" not in result
        assert "[REDACTED_EMAIL]" in result

    def test_returns_error_message_when_agent_raises(self, monkeypatch):
        fake_agent = FakeAgent(RuntimeError("model unavailable"))
        monkeypatch.setattr(diagnostic_agent, "get_diagnostic_agent", lambda: fake_agent)

        result = diagnostic_agent.diagnose_log_failure("some failure")

        assert "Diagnostic analysis failed due to error" in result
        assert "model unavailable" in result

    def test_empty_log_payload(self, monkeypatch):
        fake_agent = FakeAgent("No failure detected")
        monkeypatch.setattr(diagnostic_agent, "get_diagnostic_agent", lambda: fake_agent)

        result = diagnostic_agent.diagnose_log_failure("")

        assert result == "No failure detected"
