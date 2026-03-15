from tools.market_data import scan_market

def test_scan_market_returns_list():
    """
    Ensures the local math logic returns a valid list structure.
    In a true CI pipeline, we would mock yfinance to prevent live API calls during testing.
    """
    result = scan_market()
    assert isinstance(result, list)
    
    # If the market is completely flat, it might return empty, but if it finds something, 
    # it must conform to our schema.
    if len(result) > 0:
        first_item = result[0]
        assert "ticker" in first_item
        assert "price" in first_item
        assert "z_score" in first_item