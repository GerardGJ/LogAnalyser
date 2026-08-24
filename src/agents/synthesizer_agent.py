from src.security.pii_scrubber import scrub_text

NO_RESULTS_MESSAGE = "No results available for this question."


def synthesize_response(
    question: str,
    sql_result: str | None = None,
    diagnostic_result: str | None = None,
    errors: list[str] | None = None,
) -> str:
    """
    Merges SQL results, diagnostic summaries, and execution warnings from one
    or more upstream agents into a single concise Markdown response.

    Deterministic template assembly, not an LLM call, matching the router's
    POC decision to prefer deterministic logic for now: sections are included
    only for the routes that actually ran, in a fixed diagnostic-then-sql
    order (matching `route_query()`'s route ordering). Runs a final
    `scrub_text()` pass over the assembled Markdown before returning it, as
    the last of the PII scrub points documented in CLAUDE.md.
    """
    sections = [f"# {question.strip()}" if question and question.strip() else "# Question"]

    if diagnostic_result:
        sections.append(f"## Root Cause Analysis\n{diagnostic_result}")

    if sql_result:
        sections.append(f"## Query Results\n{sql_result}")

    if not diagnostic_result and not sql_result:
        sections.append(NO_RESULTS_MESSAGE)

    if errors:
        warnings_list = "\n".join(f"- {error}" for error in errors)
        sections.append(f"## Warnings\n{warnings_list}")

    markdown = "\n\n".join(sections)
    return scrub_text(markdown)
