from dotenv import load_dotenv
# Use create_agent directly from langchain.agents
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model

from src.tools.database import (
    sql_db_list_tables,
    sql_db_query,
    sql_db_query_checker,
    sql_db_schema,
)

load_dotenv()

MAX_RETRIES = 3

# Define tools list
tools = [sql_db_list_tables, sql_db_schema, sql_db_query, sql_db_query_checker]

# System prompt passing dialect and output limits
SYSTEM_PROMPT = """
You are an expert data analysis agent designed to interact with a DuckDB log database.

Given an input question:
1. ALWAYS inspect available tables first using `sql_db_list_tables`.
2. Inspect the schema of relevant tables using `sql_db_schema`.
3. Construct a syntactically correct DuckDB SQL query.
4. Pass your constructed query through `sql_db_query_checker` BEFORE running it.
5. Execute the checked query using `sql_db_query` and interpret the result.

Rules:
- Limit queries to at most {top_k} results unless explicitly requested otherwise.
- Only select necessary columns relevant to the question.
- Do NOT make any DML/DDL statements (INSERT, UPDATE, DELETE, DROP, ALTER).
- If a query fails or returns an error, examine the schema, correct the query, and re-check before running again.
""".format(top_k=5)


def get_sql_agent():
    """Factory function to build and return the configured SQL agent."""
    model = init_chat_model("openai:gpt-5.5")
    return create_agent(
        model=model,
        tools=[sql_db_list_tables, sql_db_schema, sql_db_query, sql_db_query_checker],
        system_prompt=SYSTEM_PROMPT,
    )

def query_log_agent_with_retry(
    question: str, 
    max_retries: int = MAX_RETRIES
) -> str:
    """
    Public entry point for querying logs. 
    Executes the agent workflow and wraps it in an explicit N-retry loop.
    """
    agent = get_sql_agent()
    current_prompt = question

    for attempt in range(1, max_retries + 1):
        try:
            print(f"\n🤖 [Attempt {attempt}/{max_retries}] Processing question...")
            
            # Execute agent graph
            result = agent.invoke({"messages": [("user", current_prompt)]})
            
            # Extract final response from agent's state
            final_message = result["messages"][-1].content
            return final_message

        except Exception as e:
            print(f"⚠️ [Attempt {attempt}/{max_retries}] Execution failed: {e}")
            
            if attempt == max_retries:
                return (
                    f"Failed to answer the question after {max_retries} attempts. "
                    f"Last error encountered: {e}"
                )
            
            # Re-prompt agent with explicit error trace context for self-correction
            current_prompt = (
                f"Original User Question: {question}\n\n"
                f"Your previous attempt generated an unhandled error: {e}.\n"
                "Please inspect the database schema again, re-check your SQL query, "
                "and fix the error before executing."
            )


if __name__ == "__main__":
    sample_question = "How did the last execution finish?"
    run_sql_agent(sample_question)