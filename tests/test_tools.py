import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from tools.market_data import process_single_ticker, scan_market

@patch('tools.market_data.yf.Ticker')
def test_process_single_ticker_anomaly(mock_ticker):
    """Test the math engine catches an anomaly and formats the dict."""
    # Mock a 30-day yfinance history dataframe with a sudden crash at the end
    prices = [150] * 29 + [100]
    mock_df = pd.DataFrame({'Close': prices}) 
    
    # Setup the mock instance to return our fake dataframe and info dict
    mock_instance = MagicMock()
    mock_instance.history.return_value = mock_df
    mock_instance.info = {"shortName": "Apple Inc.", "trailingPE": 25.5}
    mock_ticker.return_value = mock_instance
    
    # Run the synchronous function
    result = process_single_ticker("AAPL")
    
    # Assertions
    assert result is not None
    assert result['symbol'] == "AAPL"
    assert result['price'] == 100
    assert result['color'] == "pink"  

@patch('tools.market_data.yf.Ticker')
def test_process_single_ticker_noise(mock_ticker):
    """Test the math engine filters out normal market noise."""
    # Mock a completely flat 30-day history (no volatility)
    prices = [150] * 30
    mock_df = pd.DataFrame({'Close': prices}) 
    
    mock_instance = MagicMock()
    mock_instance.history.return_value = mock_df
    mock_ticker.return_value = mock_instance
    
    # Run the synchronous function
    result = process_single_ticker("AAPL")
    
    # Should return None because the Z-score won't reach the 2.0 threshold
    assert result is None

@pytest.mark.asyncio
@patch('tools.market_data.get_sp500_tickers')
@patch('tools.market_data.process_single_ticker')
async def test_scan_market_filtration(mock_process, mock_get_tickers):
    """Test that the scanner filters out noise and only returns 2-Sigma+ events."""
    # Tell the scanner to only test 3 stocks instead of 500
    mock_get_tickers.return_value = ["MSFT", "TSLA", "NVDA"]
    
    mock_process.side_effect = [
        None, 
        {"symbol": "TSLA", "zScore": -2.5, "color": "yellow"},
        {"symbol": "NVDA", "zScore": -3.5, "color": "pink"}
    ]
    
    results = await scan_market()
    
    # The scan should drop MSFT and keep TSLA and NVDA
    assert len(results) == 2
    symbols = [r['symbol'] for r in results]
    assert "MSFT" not in symbols
    assert "TSLA" in symbols