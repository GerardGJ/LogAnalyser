from src.agents.sql_agent import query_log_agent_with_retry

def main():
    user_query = "How did the last execution finish?"
    
    # Executes agent with fallback / automatic N-retry loop
    response = query_log_agent_with_retry(user_query, max_retries=3)
    
    print("\n=== AGENT RESPONSE ===")
    print(response)

if __name__ == "__main__":
    main()