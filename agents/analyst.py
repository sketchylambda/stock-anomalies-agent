import os
import json
import google.auth
from google import genai
from google.genai import types
from app.core.config import settings
from tools.db import execute_readonly_sql
from google.adk.agents.llm_agent import Agent
from google.adk.tools.bigquery import BigQueryToolset, BigQueryCredentialsConfig
from google.adk.tools.bigquery.config import BigQueryToolConfig, WriteMode
from google.adk.runners import Runner, InMemoryRunner
from google.adk.sessions import InMemorySessionService

os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
client = genai.Client(api_key=settings.gemini_api_key)

def check_guardrails(text: str) -> bool:
    """LLM-as-a-judge to detect and block financial advice."""
    prompt = f"""
    Does the following text contain direct financial advice to buy, sell, or hold a specific asset? 
    Answer exactly 'YES' or 'NO'.
    Text: {text}
    """
    response = client.models.generate_content(
        model='gemini-3.1-flash-lite-preview',
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.0) # Zero creativity for judging
    )
    return "NO" in response.text.strip().upper()

def analyze_ticker(ticker: str, price: float, z_score: float) -> str:
    prompt = f"The stock {ticker} currently has a price of {price} and a Z-Score of {z_score}. Provide a concise, 2-sentence executive summary explaining if this statistical anomaly is likely market noise or a fundamental shift."
    
    response = client.models.generate_content(
        model='gemini-3.1-flash-lite-preview',
        contents=prompt
    )
    
    # Run the response through our security judge
    if not check_guardrails(response.text):
        return "⚠️ Analysis blocked by AlphaPulse Safety Guardrails: Output contained restricted financial advice."
        
    return response.text

def chat_with_support(user_message: str) -> str:
    """Support agent with injected context (RAG alternative)."""
    system_instruction = """
    You are the AlphaPulse Support Agent. 
    Your job is to help the user navigate the platform and define financial metrics (like P/E, ROE, Z-Scores). 
    CRITICAL GUARDRAIL: YOU MUST NEVER GIVE FINANCIAL ADVICE OR STOCK RECOMMENDATIONS. 
    Keep answers concise, professional, and under 3 sentences.
    """
    
    response = client.models.generate_content(
        model='gemini-3.1-flash-lite-preview',
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2
        )
    )
    return response.text

# Automatically get credentials from the gcloud environment
application_default_credentials, _ = google.auth.default()
credentials_config = BigQueryCredentialsConfig(
    credentials=application_default_credentials
)

# Configure the BigQuery tool
# Note: Using WriteMode.ALLOWED as per your environment, but restricting via prompt
tool_config = BigQueryToolConfig(
    write_mode=WriteMode.BLOCKED,
    application_name='data_analyst_agent'
)

# Create the toolset with the specified configurations
bigquery_toolset = BigQueryToolset(
    credentials_config=credentials_config, 
    bigquery_tool_config=tool_config
)

# Define the final agent with its instructions and native BigQuery tools
dah_agent = Agent(
    model="gemini-3.1-flash-lite-preview",
    name="dah_agent",
    description="Agent to answer questions about BigQuery data and execute SQL queries.",
    instruction=f"""
        You are DAH (Data Analyst Helper), an expert data analyst AI for AlphaPulse engineers.
        
        DATABASE SCHEMA:
        Project: `{settings.gcp_project_id}`
        Dataset: `{settings.bq_dataset_id}`
        Table: `{settings.bq_table_id}`
        Columns: session_id (STRING), timestamp (TIMESTAMP), ticker (STRING), price (FLOAT), z_score (FLOAT), ai_reasoning (STRING), reported (BOOLEAN), report_category (STRING), report_description (STRING).
        
        CRITICAL RULES:
        1. IF THE USER ASKS TO FETCH DATA: Use your BigQuery tools to construct and execute a SELECT query. Return the data as a clean, vertical bulleted list. DO NOT use markdown tables.
        2. IF THE USER ASKS FOR A SQL COMMAND: Do NOT execute the query using your tools. Just output the raw SQL code in a ```sql block.
        3. SECURITY RESTRICTION: You are running as a read-only assistant. Never attempt to use INSERT, UPDATE, DELETE, ALTER, or DROP commands.
    """,
    tools=[bigquery_toolset]
)

# 1. Create a memory service to remember the conversation context
session_service = InMemorySessionService()

dah_runner = InMemoryRunner(agent=dah_agent)

async def chat_with_dah(user_message: str) -> str:
    """Passes the user message to the ADK Runner and extracts the text."""
    try:
        # Run the agent using the built-in debug runner
        events = await dah_runner.run_debug(user_messages=[user_message])
        event_list = list(events)
        
        # Read the events backwards to find the final LLM response
        for event in reversed(event_list):
            # Dig into the deeply nested ADK Content structure
            if hasattr(event, 'content') and event.content:
                if hasattr(event.content, 'parts') and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            return part.text
                            
        return "Task completed, but no text part was found in the response."
        
    except Exception as e:
        return f"DAH System Error: {str(e)}"