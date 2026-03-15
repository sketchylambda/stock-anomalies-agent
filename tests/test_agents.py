import pytest
from unittest.mock import patch, MagicMock
from agents.analyst import analyze_ticker, text_to_sql

# -------------------------------------------------------------------
# Hiring Signal: We use @patch to intercept 'model.generate_content'
# so our automated tests never hit the actual Google API.
# -------------------------------------------------------------------

@patch("agents.analyst.model.generate_content")
def test_analyze_ticker(mock_generate):
    """
    Tests that the analyst agent correctly formats its prompt and 
    handles the AI's response object.
    """
    # 1. Setup the Mock (The fake AI response)
    mock_response = MagicMock()
    mock_response.text = "This is a simulated AI analysis indicating a market overreaction."
    mock_generate.return_value = mock_response

    # 2. Execute the function
    ticker = "TSLA"
    price = 150.50
    z_score = -3.2
    result = analyze_ticker(ticker, price, z_score)

    # 3. Assertions (Did our code behave correctly?)
    assert result == "This is a simulated AI analysis indicating a market overreaction."
    
    # Check that the AI was actually called once
    mock_generate.assert_called_once()
    
    # Check that our variables made it into the prompt
    called_prompt = mock_generate.call_args[0][0]
    assert "TSLA" in called_prompt
    assert "-3.2" in called_prompt


@patch("agents.analyst.model.generate_content")
def test_text_to_sql_formatting(mock_generate):
    """
    Tests that our Text-to-SQL agent correctly strips markdown 
    formatting (like ```sql) from the AI's raw output.
    """
    # 1. Setup the Mock with messy markdown that LLMs often return
    mock_response = MagicMock()
    mock_response.text = "```sql\nSELECT * FROM anomalies WHERE ticker = 'AAPL'\n```"
    mock_generate.return_value = mock_response

    # 2. Execute the function
    user_query = "Show me Apple anomalies"
    result = text_to_sql(user_query)

    # 3. Assertions
    # The agent should have stripped the markdown formatting
    assert result == "SELECT * FROM anomalies WHERE ticker = 'AAPL'"
    assert "```" not in result