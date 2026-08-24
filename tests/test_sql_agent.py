import pytest

import src.agents.sql_agent as sql_agent


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeAgent:
    """A stand-in for the LangChain agent graph returned by `get_sql_agent()`.

    `responses` is consumed one entry per `.invoke()` call; an entry that is
    an Exception subclass instance is raised instead of returned, so tests
    can script failure-then-success retry sequences deterministically.
    """

    def __init__(self, responses):
        self.responses = list(responses)
        self.invocations = []

    def invoke(self, payload):
        self.invocations.append(payload)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return {"messages": [FakeMessage(response)]}


class TestQueryLogAgentWithRetry:
    def test_returns_final_message_on_first_success(self, monkeypatch):
        fake_agent = FakeAgent(["3 errors found in sleep_app"])
        monkeypatch.setattr(sql_agent, "get_sql_agent", lambda: fake_agent)

        result = sql_agent.query_log_agent_with_retry("how many errors?")

        assert result == "3 errors found in sleep_app"
        assert len(fake_agent.invocations) == 1

    def test_scrubs_prompt_before_sending_to_agent(self, monkeypatch):
        fake_agent = FakeAgent(["ok"])
        monkeypatch.setattr(sql_agent, "get_sql_agent", lambda: fake_agent)

        sql_agent.query_log_agent_with_retry("contact admin@example.com about errors")

        sent_prompt = fake_agent.invocations[0]["messages"][0][1]
        assert "admin@example.com" not in sent_prompt
        assert "[REDACTED_EMAIL]" in sent_prompt

    def test_retries_after_failure_and_succeeds(self, monkeypatch):
        fake_agent = FakeAgent([RuntimeError("db locked"), "recovered result"])
        monkeypatch.setattr(sql_agent, "get_sql_agent", lambda: fake_agent)

        result = sql_agent.query_log_agent_with_retry("count errors", max_retries=3)

        assert result == "recovered result"
        assert len(fake_agent.invocations) == 2
        # The re-prompt after failure must carry the original question and the error.
        retry_prompt = fake_agent.invocations[1]["messages"][0][1]
        assert "count errors" in retry_prompt
        assert "db locked" in retry_prompt

    def test_returns_failure_message_after_exhausting_retries(self, monkeypatch):
        fake_agent = FakeAgent([RuntimeError("boom"), RuntimeError("boom"), RuntimeError("boom")])
        monkeypatch.setattr(sql_agent, "get_sql_agent", lambda: fake_agent)

        result = sql_agent.query_log_agent_with_retry("count errors", max_retries=3)

        assert "Failed to answer the question after 3 attempts" in result
        assert "boom" in result
        assert len(fake_agent.invocations) == 3

    def test_agent_is_built_once_and_reused_across_retries(self, monkeypatch):
        build_calls = []

        def fake_get_sql_agent():
            agent = FakeAgent([RuntimeError("boom"), "ok"])
            build_calls.append(agent)
            return agent

        monkeypatch.setattr(sql_agent, "get_sql_agent", fake_get_sql_agent)

        sql_agent.query_log_agent_with_retry("count errors", max_retries=3)

        assert len(build_calls) == 1
