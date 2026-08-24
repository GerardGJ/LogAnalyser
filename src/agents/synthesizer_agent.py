from src.security.pii_scrubber import scrub_text
from src.utils.config_loader import get_agent_model

NO_RESULTS_MESSAGE = "No results available for this question."

_SYNTHESIS_PROMPT = """You are a Synthesizer agent for a log analysis system. Combine the SQL \
query results and the diagnostic root-cause analysis below into ONE concise, coherent Markdown \
response that directly answers the user's question. Connect the data to the root cause instead \
of repeating both sections verbatim.

User Question: {question}

SQL Query Results:
{sql_result}

Diagnostic Root-Cause Analysis:
{diagnostic_result}
{warnings_block}
Respond with the final Markdown answer only, no preamble."""


def _assemble_markdown(
    question: str,
    sql_result: str | None,
    diagnostic_result: str | None,
    errors: list[str] | None,
) -> str:
    """Deterministic template assembly: renders only the sections for routes
    that actually produced a result, in diagnostic-before-sql order matching
    `route_query()`."""
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

    return "\n\n".join(sections)


def _synthesize_with_llm(
    question: str,
    sql_result: str,
    diagnostic_result: str,
    errors: list[str] | None,
) -> str:
    """Uses a model to weave the SQL results and diagnostic analysis into one
    narrative, rather than the two sections just being concatenated. Only
    called when both routes produced a result — with just one, there's
    nothing to reconcile and the deterministic template is enough."""
    warnings_block = ""
    if errors:
        warnings_block = "\nWarnings:\n" + "\n".join(f"- {error}" for error in errors) + "\n"

    prompt = _SYNTHESIS_PROMPT.format(
        question=question.strip() if question else "",
        sql_result=sql_result,
        diagnostic_result=diagnostic_result,
        warnings_block=warnings_block,
    )

    model = get_agent_model("synthesizer_agent")
    response = model.invoke(prompt)
    return response.content if hasattr(response, "content") else str(response)


def synthesize_response(
    question: str,
    sql_result: str | None = None,
    diagnostic_result: str | None = None,
    errors: list[str] | None = None,
) -> str:
    """
    Merges SQL results, diagnostic summaries, and execution warnings from one
    or more upstream agents into a single concise Markdown response.

    Deterministic template assembly handles every case except one: when both
    a SQL result and a diagnostic result are present, a model is used
    instead to produce one coherent narrative connecting the data to the
    root cause, rather than just concatenating the two sections. If that
    model call fails for any reason, this falls back to the deterministic
    template so a response is still returned.

    Runs a final `scrub_text()` pass over the assembled Markdown before
    returning it, as the last of the PII scrub points documented in
    CLAUDE.md.
    """
    if sql_result and diagnostic_result:
        try:
            markdown = _synthesize_with_llm(question, sql_result, diagnostic_result, errors)
        except Exception:
            markdown = _assemble_markdown(question, sql_result, diagnostic_result, errors)
    else:
        markdown = _assemble_markdown(question, sql_result, diagnostic_result, errors)

    return scrub_text(markdown)
