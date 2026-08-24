import polars as pl

from src.security.pii_scrubber import scrub_dataframe, scrub_text


class TestScrubText:
    def test_redacts_email(self):
        result = scrub_text("Contact user at jane.doe@example.com for details")
        assert "jane.doe@example.com" not in result
        assert "[REDACTED_EMAIL]" in result

    def test_redacts_ipv4(self):
        result = scrub_text("Request originated from 192.168.1.100")
        assert "192.168.1.100" not in result
        assert "[REDACTED_IP]" in result

    def test_redacts_jwt(self):
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PYb9lZDLQ7Y"
        result = scrub_text(f"Authorization token: {jwt}")
        assert jwt not in result
        assert "[REDACTED_JWT]" in result

    def test_redacts_bearer_token(self):
        result = scrub_text("Authorization: Bearer abcdefghijklmnopqrstuvwx1234")
        assert "abcdefghijklmnopqrstuvwx1234" not in result
        assert "[REDACTED_API_KEY]" in result

    def test_redacts_api_key(self):
        result = scrub_text("api_key=abcdefghijklmnopqrstuvwx")
        assert "abcdefghijklmnopqrstuvwx" not in result
        assert "[REDACTED_API_KEY]" in result

    def test_leaves_clean_text_unchanged(self):
        text = "Pipeline finished successfully with no errors"
        assert scrub_text(text) == text

    def test_non_string_input_passthrough(self):
        assert scrub_text(None) is None
        assert scrub_text(123) == 123

    def test_redacts_multiple_pii_types_in_one_string(self):
        result = scrub_text(
            "User jane.doe@example.com connected from 10.0.0.5 with api_key=abcdefghijklmnopqrstuvwx"
        )
        assert "jane.doe@example.com" not in result
        assert "10.0.0.5" not in result
        assert "abcdefghijklmnopqrstuvwx" not in result
        assert "[REDACTED_EMAIL]" in result
        assert "[REDACTED_IP]" in result
        assert "[REDACTED_API_KEY]" in result


class TestScrubDataframe:
    def test_redacts_email_column(self):
        df = pl.DataFrame({"message": ["contact jane.doe@example.com"]})
        result = scrub_dataframe(df)
        assert result["message"][0] == "contact [REDACTED_EMAIL]"

    def test_redacts_ipv4_column(self):
        df = pl.DataFrame({"message": ["from 192.168.1.100"]})
        result = scrub_dataframe(df)
        assert result["message"][0] == "from [REDACTED_IP]"

    def test_redacts_jwt_column(self):
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PYb9lZDLQ7Y"
        df = pl.DataFrame({"message": [f"token: {jwt}"]})
        result = scrub_dataframe(df)
        assert jwt not in result["message"][0]
        assert "[REDACTED_JWT]" in result["message"][0]

    def test_redacts_bearer_token_column(self):
        df = pl.DataFrame({"message": ["Authorization: Bearer abcdefghijklmnopqrstuvwx1234"]})
        result = scrub_dataframe(df)
        assert "abcdefghijklmnopqrstuvwx1234" not in result["message"][0]
        assert "[REDACTED_API_KEY]" in result["message"][0]

    def test_redacts_api_key_column(self):
        df = pl.DataFrame({"message": ["api_key=abcdefghijklmnopqrstuvwx"]})
        result = scrub_dataframe(df)
        assert result["message"][0] == "api_key=[REDACTED_API_KEY]"

    def test_only_scrubs_target_columns_when_specified(self):
        df = pl.DataFrame(
            {
                "message": ["contact jane.doe@example.com"],
                "app": ["jane.doe@example.com"],
            }
        )
        result = scrub_dataframe(df, target_columns=["message"])
        assert result["message"][0] == "contact [REDACTED_EMAIL]"
        assert result["app"][0] == "jane.doe@example.com"

    def test_auto_detects_all_string_columns(self):
        df = pl.DataFrame(
            {
                "message": ["contact jane.doe@example.com"],
                "app": ["from 192.168.1.100"],
                "line_number": [42],
            }
        )
        result = scrub_dataframe(df)
        assert result["message"][0] == "contact [REDACTED_EMAIL]"
        assert result["app"][0] == "from [REDACTED_IP]"
        assert result["line_number"][0] == 42

    def test_non_pii_dataframe_unchanged(self):
        df = pl.DataFrame({"message": ["pipeline finished successfully"]})
        result = scrub_dataframe(df)
        assert result["message"][0] == "pipeline finished successfully"

    def test_empty_dataframe(self):
        df = pl.DataFrame({"message": []}, schema={"message": pl.String})
        result = scrub_dataframe(df)
        assert result.is_empty()
