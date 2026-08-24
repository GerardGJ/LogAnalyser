import pytest

from src.agents.router_agent import route_query


class TestMetricsQueriesRouteToSql:
    @pytest.mark.parametrize(
        "question",
        [
            "how many errors happened today",
            "count errors by app",
            "list all warnings from sleep_app",
            "what is the average response time",
            "show me the top 5 apps by error count",
            "group by level and count",
        ],
    )
    def test_routes_to_sql(self, question):
        assert route_query(question) == ["sql"]


class TestRootCauseQueriesRouteToDiagnostic:
    @pytest.mark.parametrize(
        "question",
        [
            "why did the pipeline fail",
            "what caused this crash",
            "the service broke, what happened",
            "diagnose the exception in train.py",
            "help me debug this traceback",
            "what is the root cause of the failure",
        ],
    )
    def test_routes_to_diagnostic(self, question):
        assert route_query(question) == ["diagnostic"]


class TestTraceLookupQueriesRouteToSql:
    @pytest.mark.parametrize(
        "question",
        [
            "show events from source_file train.py",
            "list records where source_file is main.py",
        ],
    )
    def test_routes_to_sql_not_diagnostic(self, question):
        # "trace"/"source_file" lookups are filtered SELECTs, not root-cause
        # analysis, even though they sound trace-related.
        assert route_query(question) == ["sql"]


class TestAmbiguousInputsRouteToUnsupported:
    @pytest.mark.parametrize(
        "question",
        [
            "",
            "   ",
            "hello there",
            "what is the weather today",
        ],
    )
    def test_routes_to_unsupported(self, question):
        assert route_query(question) == []

    def test_empty_string(self):
        assert route_query("") == []


class TestCaseInsensitivity:
    def test_uppercase_sql_keywords_match(self):
        assert route_query("HOW MANY ERRORS TODAY") == ["sql"]

    def test_uppercase_diagnostic_keywords_match(self):
        assert route_query("WHY DID THIS CRASH") == ["diagnostic"]


class TestWordBoundaryFalsePositives:
    def test_fail_does_not_match_inside_failover(self):
        # "failover" contains "fail" as a substring but is not itself a
        # failure-intent word; the router should not treat it as diagnostic
        # in isolation unless another diagnostic phrase also appears.
        assert route_query("configure failover for the database cluster") == []

    def test_why_does_not_match_inside_another_word(self):
        assert route_query("anywhy is not a real question") == []


class TestMixedIntentReturnsBothRoutes:
    def test_both_routes_present_in_diagnostic_before_sql_order(self):
        question = "why are there so many errors, show me the top 5 apps"
        assert route_query(question) == ["diagnostic", "sql"]

    def test_sql_only_question_does_not_include_diagnostic(self):
        assert route_query("count errors by app") == ["sql"]

    def test_diagnostic_only_question_does_not_include_sql(self):
        assert route_query("why did the pipeline fail") == ["diagnostic"]
