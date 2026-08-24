from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain.tools import tool

from config.settings import DUCKDB_PATH
from src.engines.duckdb_engine import DuckDBEngine
from src.utils.config_loader import get_agent_model

load_dotenv()

# Initialize model instance for internal tool invocation
engine = DuckDBEngine(DUCKDB_PATH)

@tool
def sql_db_list_tables() -> str:
    """Input is an empty string, output is a comma-separated list of tables in the database."""
    try:
        with engine:
            tables = engine.execute_query("SHOW TABLES")
        tables = [row for row in tables["name"]]
        return ", ".join(tables)
    except Exception as e:
        return f"Error listing tables: {e}"

@tool
def sql_db_schema(table_names: str) -> str:
    """Input to this tool is a comma-separated list of tables, output is the schema and sample rows for those tables.
    Be sure that the tables actually exist by calling sql_db_list_tables first!
    Example Input: table1, table2, table3"""
    results = []
    tables = [t.strip() for t in table_names.split(",") if t.strip()]

    try:
        with engine:
            for table in tables:
                try:
                    schema_df = engine.get_schema(table)

                    examples_df = engine.execute_query(f'SELECT * FROM "{table}" LIMIT 3;')
                    schema_str = "\n".join(
                        f"  {row['column_name']}: {row['column_type']}" 
                        for row in schema_df.iter_rows(named=True)
                    )
                    
                    sample_str = ""
                    if not examples_df.is_empty():
                        headers = "\t".join(examples_df.columns)
                        rows = "\n".join(
                            "\t".join(str(val) for val in row) 
                            for row in examples_df.iter_rows()
                        )
                        sample_str = f"\nSample rows:\n{headers}\n{rows}"

                    results.append(f"Table '{table}' Schema:\n{schema_str}\n{sample_str}")
                except Exception as e:
                    results.append(f"Error fetching schema/samples for table '{table}': {e}")
        return "\n\n".join(results)
    except Exception as e:
        return f"Error connecting to database: {e}"

@tool
def sql_db_query(query: str) -> str:
    """Input to this tool is a detailed and correct SQL query, output is a result from the database.
    If the query is not correct, an error message will be returned.
    If an error is returned, rewrite the query, check the query, and try again.
    If you encounter an issue with Unknown column 'xxxx' in 'field list', use sql_db_schema to query the correct table fields."""
    try:
        with engine:
            res = engine.execute_query(query)
            if res.is_empty():
                return "Query executed successfully. Result is empty."
            return str(res)
    except Exception as e:
        return f"Error executing query: {e}"

@tool
def sql_db_query_checker(query: str) -> str:
    """Use this tool to double check if your query is correct before executing it.
    Always use this tool before executing a query with sql_db_query!"""
    trigger_prompt =f"""Double check the following DuckDB SQL query for common mistakes, including:
- Using NOT IN with NULL values
- Using UNION when UNION ALL should have been used
- Using BETWEEN for exclusive ranges
- Data type mismatch in predicates
- Properly quoting identifiers and table names
- Using the correct number of arguments for functions
- Casting to the correct data type
- Using valid DuckDB dialect syntax

If there are any mistakes, rewrite the query. If there are no mistakes, reproduce the original query.

Output the final executable SQL query only, without explanation or markdown formatting.

SQL Query:
{query}"""
    
    model = get_agent_model("query_checker")
    response = model.invoke(trigger_prompt)
    content = response.content if hasattr(response, "content") else str(response)
    
    # Clean output by removing backticks and leading/trailing whitespace
    clean_sql = (
        content.strip()
        .removeprefix("```sql")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )
    return clean_sql