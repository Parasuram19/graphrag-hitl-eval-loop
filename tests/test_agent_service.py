# tests/test_agent_service.py
import pytest
from unittest.mock import MagicMock
from app.services.agent_service import AgentService

def test_run_query_handles_graph_error_gracefully():
    """Validates that if the graph fails, the agent returns an error state instead of crashing."""
    mock_agent = MagicMock()
    
    # Simulate LangGraph returning an error state from the retrieve node
    mock_agent.invoke.return_value = {
        "error": "Retrieval failed: Neo4j connection timeout",
        "generated_answer": "An error occurred during retrieval.",
        "retrieved_results": [],
        "citations": [],
        "graph_evidence": [],
        "vector_hits": 0,
        "graph_hits": 0
    }
    
    service = AgentService(agent=mock_agent)
    result = service.run_query(query="test query")
    
    # The API should return the error cleanly, not throw a 500
    assert result["error"] is not None
    
    # FIX: Check for "failed" or "error" since the actual app returns "Retrieval failed: ..."
    assert "failed" in result["error"].lower() or "error" in result["error"].lower()