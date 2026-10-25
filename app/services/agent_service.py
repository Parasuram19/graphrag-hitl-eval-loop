import uuid
from typing import Any, Dict, Optional

from langgraph.graph.state import CompiledStateGraph
from app.agents.graphrag_agent import GraphRAGState


class AgentService:
    def __init__(self, agent: CompiledStateGraph):
        self.agent = agent

    def run_query(self, query: str, user_id: Optional[str] = None, user_roles: Optional[list[str]] = None, top_k: int = 5) -> Dict[str, Any]:
        
        interaction_id = str(uuid.uuid4())

        initial_state: GraphRAGState = {
            "interaction_id": interaction_id,
            "query": query,
            "user_id": user_id,
            "user_roles": user_roles or [],
            "top_k": top_k,
            "retrieved_results": [],
            "graph_evidence": [],
            "citations": [],
            "vector_hits": 0,
            "graph_hits": 0,
            "terms": [],
            "generated_answer": "",
            "confidence": 0.0,
            "reasoning": "",
            "error": None,
        }

        final_state = self.agent.invoke(initial_state)
        
        # DEBUG: Print what the graph actually returned
        print(f"DEBUG: Graph returned keys: {list(final_state.keys())}")
        print(f"DEBUG: interaction_id in final_state: {final_state.get('interaction_id')}")

        return {
            "interaction_id": interaction_id, # Always return the one we generated
            "query": final_state.get("query"),
            "answer": final_state.get("generated_answer"),
            "confidence": final_state.get("confidence"),
            "reasoning": final_state.get("reasoning"),
            "citations": final_state.get("citations", []),
            "graph_evidence": final_state.get("graph_evidence", []),
            "retrieval_stats": {
                "vector_hits": final_state.get("vector_hits", 0),
                "graph_hits": final_state.get("graph_hits", 0),
                "fused_results": len(final_state.get("retrieved_results", [])),
            },
            "error": final_state.get("error"),
        }