import pytest
from unittest.mock import patch, AsyncMock
from agents.analyst import check_guardrails, analyze_ticker, chat_with_support, chat_with_dah

# Create a robust fake response object for our mocked Gemini client
class FakeGenAIResponse:
    def __init__(self, text):
        self.text = text

def test_security_guardrail_safe():
    """Test that the guardrail returns True when the judge says 'NO' (no financial advice)."""
    with patch('agents.analyst.client.models.generate_content') as mock_gen:
        # Mock the judge answering 'NO' to the safety prompt
        mock_gen.return_value = FakeGenAIResponse("NO")
        
        result = check_guardrails("Just some educational context about the stock.")
        
        assert result is True

def test_security_guardrail_blocked():
    """Test that the guardrail returns False when the judge says 'YES' (financial advice detected)."""
    with patch('agents.analyst.client.models.generate_content') as mock_gen:
        # Mock the judge answering 'YES' to the safety prompt
        mock_gen.return_value = FakeGenAIResponse("YES")
        
        result = check_guardrails("You should buy this stock right now.")
        
        assert result is False

def test_analyze_ticker_integration():
    """Test the full Analyst pipeline to ensure the Guardrail successfully intercepts bad output."""
    with patch('agents.analyst.client.models.generate_content') as mock_gen:

        mock_gen.side_effect = [
            FakeGenAIResponse("NVDA is a strong buy at this level."),
            FakeGenAIResponse("YES")
        ]
        
        result = analyze_ticker("NVDA", 100.0, -3.5)
        
        assert "blocked by AlphaPulse Safety Guardrails" in result

@patch('agents.analyst.client.models.generate_content')
def test_support_agent_prompting(mock_gen):
    """Test that the Support Agent returns the expected context."""
    mock_gen.return_value = FakeGenAIResponse("A Z-score measures standard deviations from the mean.")
    
    response = chat_with_support("What is a Z-score?")
    
    assert "standard deviations" in response
    mock_gen.assert_called_once()

@pytest.mark.asyncio
@patch('agents.analyst.dah_runner.run_debug', new_callable=AsyncMock)
async def test_dah_agent_execution(mock_run_debug):
    """Test the ADK DAH Agent setup and extraction logic."""
    
    class FakePart:
        text = "- NVDA: -3.5"
    class FakeContent:
        parts = [FakePart()]
    class FakeEvent:
        content = FakeContent()
        
    # run_debug returns an iterable list of events
    mock_run_debug.return_value = [FakeEvent()]
    
    response = await chat_with_dah("List stocks below -2.0 Z-score")
    
    assert "NVDA" in response
    mock_run_debug.assert_called_once()