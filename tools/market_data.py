import pandas as pd
import requests
import yfinance as yf
import asyncio
import datetime
import pytz

def get_sp500_tickers():
    """Dynamically scrapes the live S&P 500 list from Wikipedia using a custom User-Agent."""
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        
        # 1. Put on the fake mustache (Pretend to be Chrome on Windows)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # 2. Fetch the page using requests with our fake headers
        response = requests.get(url, headers=headers)
        response.raise_for_status() # Ensure the request actually succeeded
        
        # 3. Pass the raw HTML text into pandas instead of the URL
        table = pd.read_html(response.text)[0]
        tickers = table['Symbol'].tolist()
        
        # 4. Fix Yahoo Finance hyphen formatting
        tickers = [ticker.replace('.', '-') for ticker in tickers]
        
        return tickers
        
    except Exception as e:
        print(f"Error fetching S&P 500 list: {e}")
        # Fallback to a safe list if the connection fails
        return [
            "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "LLY", "AVGO", "V", 
            "JPM", "WMT", "JNJ", "MA", "PG", "HD", "COST", "MRK", "ABBV", "CRM", 
            "CVX", "NFLX", "AMD", "PEP", "KO", "BAC", "TMO", "WFC", "DIS", "MCD", 
            "CSCO", "ABT", "INTC", "INTU", "AMAT", "IBM", "CMCSA", "QCOM", "TXN", "VZ", 
            "NOW", "AMGN", "PFE", "BA", "UNP", "HON", "SYK", "ELV", "BKNG", "SNOW"
        ]

def process_single_ticker(ticker):
    """The synchronous math engine for a single stock."""
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="1mo")
        if data.empty: return None
        
        mean = data['Close'].mean()
        std = data['Close'].std()
        current_price = data['Close'].iloc[-1]
        z_score = (current_price - mean) / std
        
        if abs(z_score) >= 2.0:
            if abs(z_score) >= 3.0:
                severity = "3-Sigma (Extreme)"
                color_tier = "pink"
            else:
                severity = "2-Sigma (Elevated)"
                color_tier = "yellow"

            info = stock.info
            return {
                "symbol": ticker,
                "name": info.get("shortName", ticker),
                "price": round(current_price, 2),
                "zScore": round(z_score, 2),
                "severity": severity,
                "color": color_tier,
                "pe": round(info.get("trailingPE", 0), 2) if info.get("trailingPE") else "N/A",
                "roe": f"{round(info.get('returnOnEquity', 0) * 100, 2)}%" if info.get('returnOnEquity') else "N/A",
                "de": round(info.get("debtToEquity", 0) / 100, 2) if info.get("debtToEquity") else "N/A",
                "website": info.get("website", f"https://finance.yahoo.com/quote/{ticker}")
            }
    except Exception:
        # Silently skip errors (like delisted stocks) to keep the scanner moving fast
        return None
    return None

async def fetch_with_semaphore(semaphore, ticker):
    """Controls the speed limit and pushes the blocking task to a background thread."""
    async with semaphore:
        # to_thread prevents yfinance from freezing the FastAPI event loop
        return await asyncio.to_thread(process_single_ticker, ticker)

async def scan_market():
    """Concurrently scans the entire S&P 500 in seconds."""
    # We can finally run the whole list!
    tickers = get_sp500_tickers()
    
    # Bouncer: Only allow 20 simultaneous connections to Yahoo Finance
    semaphore = asyncio.Semaphore(20)
    
    # Create all 500 background tasks
    tasks = [fetch_with_semaphore(semaphore, ticker) for ticker in tickers]
    
    # Run them all at once and wait for the results
    results = await asyncio.gather(*tasks)
    
    # Filter out the "None" values (stocks that weren't anomalous)
    anomalies = [res for res in results if res is not None]
    
    return anomalies

def get_market_status() -> dict:
    """Determines if the US market is open and calculates the S&P 500 trend."""
    # Check US Eastern Time
    ny_time = datetime.datetime.now(pytz.timezone('US/Eastern'))
    is_weekday = ny_time.weekday() < 5
    is_open = is_weekday and (9 <= ny_time.hour <= 16)
    if ny_time.hour == 9 and ny_time.minute < 30: is_open = False
    if ny_time.hour == 16 and ny_time.minute > 0: is_open = False

    # Check S&P 500 Trend (^GSPC)
    try:
        sp500 = yf.Ticker('^GSPC')
        hist = sp500.history(period='5d')
        if len(hist) >= 2:
            last_close = hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2]
            is_bull = last_close >= prev_close
        else:
            is_bull = True
    except:
        is_bull = True # Fallback

    return {"is_open": is_open, "is_bull": bool(is_bull)}