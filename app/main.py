import secrets
import time
from fastapi import FastAPI, HTTPException, Depends, status, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from tools.market_data import scan_market
from tools.db import insert_anomaly, get_cached_analysis, get_admin_stats
from agents.analyst import analyze_ticker, chat_with_support
from tools.market_data import get_market_status
from tools.db import update_anomaly_report
from agents.analyst import analyze_ticker, chat_with_support, chat_with_dah

from fastapi import Response
from google.cloud import bigquery
import pandas as pd
from app.core.config import settings 

app = FastAPI(title="AlphaPulse API", version="2.0.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# --- Enterprise Session Management ---
ACTIVE_SESSIONS = {}
SESSION_DURATION = 1800 

class LoginRequest(BaseModel):
    username: str
    password: str

def verify_admin_session(request: Request):
    """Validates the secure cookie and checks for expiration."""
    token = request.cookies.get("admin_session")
    
    if not token or token not in ACTIVE_SESSIONS:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    # Check if the 30-minute session expired on the server side
    if time.time() > ACTIVE_SESSIONS[token]:
        del ACTIVE_SESSIONS[token] # Clean up
        raise HTTPException(status_code=401, detail="Session expired")
        
    # Refresh the session timer on activity (Rolling Window)
    ACTIVE_SESSIONS[token] = time.time() + SESSION_DURATION
    return True

@app.post("/api/v1/admin/login")
def login(req: LoginRequest, response: Response):
    """Authenticates user and issues a secure HttpOnly cookie."""
    correct_username = secrets.compare_digest(req.username, "admin")
    correct_password = secrets.compare_digest(req.password, "pulse2026")
    
    if not (correct_username and correct_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    # Generate a cryptographically secure token
    token = secrets.token_hex(32)
    ACTIVE_SESSIONS[token] = time.time() + SESSION_DURATION
    
    # Set an HttpOnly cookie (invisible to Javascript, highly secure against XSS)
    response.set_cookie(key="admin_session", value=token, max_age=SESSION_DURATION, httponly=True, samesite="lax")
    return {"status": "success"}

@app.post("/api/v1/admin/logout")
def logout(request: Request, response: Response):
    """Destroys the session and clears the cookie."""
    token = request.cookies.get("admin_session")
    if token in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[token]
    response.delete_cookie("admin_session")
    return {"status": "success"}

class ChatRequest(BaseModel):
    message: str

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    with open("app/static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/admin", response_class=HTMLResponse)
async def serve_admin():
    with open("app/static/admin.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/v1/admin/stats", dependencies=[Depends(verify_admin_session)])
def fetch_admin_dashboard_data():
    """Powers the Admin UI with live BigQuery data."""
    try:
        data = get_admin_stats()
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/scan")
async def trigger_scan():
    anomalies = await scan_market()
    return {"status": "success", "data": anomalies}

@app.post("/api/v1/analyze/{ticker}")
def run_analysis(ticker: str, price: float, z_score: float, session_id: str):
    try:
        # Check the Enterprise Vault (BigQuery Cache) first
        cached_reasoning = get_cached_analysis(session_id, ticker)
        
        if cached_reasoning:
            print(f"CACHE HIT: Retrieved {ticker} from BigQuery. 0 Tokens used.")
            return {"ticker": ticker, "reasoning": cached_reasoning, "cached": True}
            
        # If no cache exists, run the expensive Gemini Agent
        print(f"CACHE MISS: Generating new Gemini analysis for {ticker}...")
        reasoning = analyze_ticker(ticker, price, z_score)
        
        # Save the new reasoning to BigQuery so it's cached for next time
        insert_anomaly(session_id, ticker, price, z_score, reasoning)
        
        return {"ticker": ticker, "reasoning": reasoning, "cached": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/support")
def support_chat(request: ChatRequest):
    try:
        reply = chat_with_support(request.message)
        return {"reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
class ReportRequest(BaseModel):
    session_id: str
    category: str
    description: str = ""

@app.get("/api/v1/market-status")
def market_status():
    return get_market_status()

@app.post("/api/v1/report/{ticker}")
def submit_report(ticker: str, req: ReportRequest):
    try:
        update_anomaly_report(req.session_id, ticker, req.category, req.description)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/admin/dah", dependencies=[Depends(verify_admin_session)])
async def dah_chat(request: ChatRequest):
    try:
        reply = await chat_with_dah(request.message)
        return {"reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# Initialize the BigQuery client
bq_client = bigquery.Client(project=settings.gcp_project_id)

@app.get("/api/v1/admin/export-logs")
async def export_reported_logs():
    """Fetches reported anomalies from BigQuery and returns a downloadable CSV."""
    try:
        # The exact query the ADK agent used earlier!
        query = f"""
            SELECT * FROM `{settings.gcp_project_id}.{settings.bq_dataset_id}.{settings.bq_table_id}` 
            WHERE reported = TRUE
            ORDER BY timestamp DESC
        """
        
        # 1. Run the query and instantly convert the results to a Pandas DataFrame
        df = bq_client.query(query).to_dataframe(create_bqstorage_client=False)
        
        # 2. Convert the DataFrame into a raw CSV string
        csv_data = df.to_csv(index=False)
        
        # 3. Return a special File Response telling the browser to download it
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=alphapulse_reported_logs.csv"
            }
        )
    except Exception as e:
        return {"error": f"Failed to generate CSV: {str(e)}"}