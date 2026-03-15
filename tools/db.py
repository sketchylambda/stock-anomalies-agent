import os
import google.auth
from google.cloud import bigquery
from app.core.config import settings

if os.path.exists("gcp-credentials.json"):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "gcp-credentials.json"

credentials, project = google.auth.default()
client = bigquery.Client(project=settings.gcp_project_id)
FULL_TABLE_PATH = f"{settings.gcp_project_id}.{settings.bq_dataset_id}.{settings.bq_table_id}"

def get_cached_analysis(session_id: str, ticker: str):
    """Checks BigQuery to see if we already generated a brief for this stock in this session."""
    query = f"""
        SELECT ai_reasoning 
        FROM `{FULL_TABLE_PATH}` 
        WHERE session_id = @session_id AND ticker = @ticker
        ORDER BY timestamp DESC
        LIMIT 1
    """
    
    # Using parameterized queries to prevent SQL injection
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("session_id", "STRING", session_id),
            bigquery.ScalarQueryParameter("ticker", "STRING", ticker),
        ]
    )
    
    query_job = client.query(query, job_config=job_config)
    results = list(query_job.result())
    
    if results:
        return results[0].ai_reasoning
    return None

def insert_anomaly(session_id: str, ticker: str, price: float, z_score: float, reasoning: str) -> bool:
    """Logs the new analysis to BigQuery with the session ID attached."""
    rows_to_insert = [{
        "timestamp": "AUTO", 
        "session_id": session_id, 
        "ticker": ticker,
        "z_score": z_score,
        "price": price,
        "ai_reasoning": reasoning
    }]
    errors = client.insert_rows_json(FULL_TABLE_PATH, rows_to_insert)
    return len(errors) == 0

def get_admin_stats():
    """Fetches the latest intelligence logs and report status from the BigQuery Vault."""
    query = f"""
        SELECT session_id, timestamp, ticker, price, z_score, ai_reasoning, 
               reported, report_category, report_description
        FROM `{FULL_TABLE_PATH}` 
        ORDER BY timestamp DESC 
        LIMIT 100
    """
    
    query_job = client.query(query)
    
    results = []
    for row in query_job:
        row_dict = dict(row)
        
        ts = row_dict.get('timestamp')
        if hasattr(ts, 'strftime'):
            row_dict['timestamp'] = ts.strftime("%b %d, %H:%M")
        else:
            row_dict['timestamp'] = str(ts)
            
        results.append(row_dict)
        
    return results

def update_anomaly_report(session_id: str, ticker: str, category: str, description: str):
    """Updates an existing intelligence log with user feedback."""
    query = f"""
        UPDATE `{FULL_TABLE_PATH}`
        SET reported = TRUE, report_category = @category, report_description = @description
        WHERE session_id = @session_id AND ticker = @ticker
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("category", "STRING", category),
            bigquery.ScalarQueryParameter("description", "STRING", description or ""),
            bigquery.ScalarQueryParameter("session_id", "STRING", session_id),
            bigquery.ScalarQueryParameter("ticker", "STRING", ticker),
        ]
    )
    client.query(query, job_config=job_config).result() # Wait for the update to complete
    return True

def execute_readonly_sql(query: str) -> str:
    """
    Executes a read-only SQL query against the BigQuery database and returns the results.
    The AI agent uses this tool to fetch actual data for the user.
    """
    query_upper = query.upper()
    forbidden_words = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "CREATE", "GRANT"]
    if any(word in query_upper for word in forbidden_words):
        return "ERROR: Query blocked by Python security policy. Only SELECT statements are allowed."
    
    # 2. Execute the query
    try:
        query_job = client.query(query)
        # Convert the results into a list of dictionaries so the AI can read it
        results = [dict(row) for row in query_job.result()]
        
        # Format timestamps so they don't break the JSON parser
        for row in results:
            for key, val in row.items():
                if hasattr(val, 'strftime'):
                    row[key] = val.strftime("%Y-%m-%d %H:%M:%S")
                    
        return str(results)
    except Exception as e:
        return f"ERROR executing query: {str(e)}"