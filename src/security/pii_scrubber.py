import re
from typing import Union
import polars as pl

# Regular expressions for sensitive PII targets
IPV4_REGEX = r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"
EMAIL_REGEX = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
# Matches common API key patterns (e.g., sk-..., api_key=..., bearer tokens)
API_KEY_REGEX = r"(?i)\b(api[_-]?key|bearer|secret|token)[\s=:]+['\"]?([A-Za-z0-9_\-]{16,})['\"]?"
# Matches standard JWT structure (header.payload.signature)
JWT_REGEX = r"\beyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\b"

# Redaction placeholders
REDACTED_IP = "[REDACTED_IP]"
REDACTED_EMAIL = "[REDACTED_EMAIL]"
REDACTED_KEY = r"\1=[REDACTED_API_KEY]"
REDACTED_JWT = "[REDACTED_JWT]"


def scrub_text(text: str) -> str:
    """
    Scubs PII (IPs, Emails, API Keys, JWT tokens) from a raw string input.
    
    Args:
        text: The raw log message or prompt string.
        
    Returns:
        The sanitized text string with sensitive data masked.
    """
    if not isinstance(text, str):
        return text

    # Redact JWTs first (to avoid conflict with general token regexes)
    text = re.sub(JWT_REGEX, REDACTED_JWT, text)
    # Redact API Keys
    text = re.sub(API_KEY_REGEX, REDACTED_KEY, text)
    # Redact Email Addresses
    text = re.sub(EMAIL_REGEX, REDACTED_EMAIL, text)
    # Redact IPv4 Addresses
    text = re.sub(IPV4_REGEX, REDACTED_IP, text)

    return text


def scrub_dataframe(
    df: pl.DataFrame, target_columns: list[str] = None
) -> pl.DataFrame:
    """
    Applies PII scrubbing natively across Polars DataFrame string columns using expressions.
    
    Args:
        df: Input Polars DataFrame containing log records.
        target_columns: Specific columns to sanitize. Defaults to all string columns.
        
    Returns:
        A new Polars DataFrame with redacted values.
    """
    if target_columns is None:
        # Auto-detect all string columns (e.g., 'message', 'raw_log')
        target_columns = [
            col for col, dtype in zip(df.columns, df.dtypes) if dtype == pl.String
        ]

    exprs = []
    for col in target_columns:
        expr = (
            pl.col(col)
            .str.replace_all(JWT_REGEX, REDACTED_JWT)
            .str.replace_all(API_KEY_REGEX, REDACTED_KEY)
            .str.replace_all(EMAIL_REGEX, REDACTED_EMAIL)
            .str.replace_all(IPV4_REGEX, REDACTED_IP)
        )
        exprs.append(expr)

    return df.with_columns(exprs)