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


def run_sql_agent(question: str):
    # Initialize the model using a supported string or provider instance
    model = init_chat_model("openai:gpt-5.5")

    # Create the agent using the recommended create_agent factory
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
    )

    print(f"\n--- Question: {question} ---\n")

    # Stream agent graph execution events
    for event in agent.stream(
        {"messages": [("user", question)]},
        stream_mode="values",
    ):
        latest_message = event["messages"][-1]

        if latest_message.type == "ai" and latest_message.tool_calls:
            for tool_call in latest_message.tool_calls:
                print(f"🔧 Tool Call: {tool_call['name']}({tool_call['args']})")
        elif latest_message.type == "tool":
            print(f"📥 Tool Output [{latest_message.name}]: {latest_message.content}\n")
        elif latest_message.type == "ai" and latest_message.content:
            print(f"\n🤖 Final Answer:\n{latest_message.content}")


if __name__ == "__main__":
    sample_question = "How did the last execution finish?"
    run_sql_agent(sample_question)