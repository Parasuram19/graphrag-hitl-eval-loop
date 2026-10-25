import uuid
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.llm_client import call_llm
from app.services.retrieval_service import RetrievalService
from app.services.feedback_service import FeedbackService
from app.schemas.retrieval import RetrievalRequest


class GraphRAGState(TypedDict, total=False):
    query: str
    user_id: Optional[str]
    user_roles: List[str]
    top_k: int
    interaction_id: str  # Must be explicitly defined
    retrieved_results: List[Dict[str, Any]]
    graph_evidence: List[Dict[str, Any]]
    citations: List[str]
    vector_hits: int
    graph_hits: int
    terms: List[str]
    generated_answer: str
    confidence: float
    reasoning: str
    error: Optional[str]


def create_retrieve_node(retrieval_service: RetrievalService):
    def retrieve_node(state: GraphRAGState) -> Dict[str, Any]:
        try:
            request = RetrievalRequest(
                query=state["query"],
                top_k=state.get("top_k", 5),
                user_id=state.get("user_id"),
                user_roles=state.get("user_roles", []),
            )
            response = retrieval_service.retrieve(request)

            return {
                # FIX: Explicitly pass the interaction_id through the delta update
                "interaction_id": state.get("interaction_id"),
                "retrieved_results": [r.model_dump() for r in response.results],
                "graph_evidence": [
                    {"chunk_id": r.chunk_id, "matched_entities": r.matched_entities}
                    for r in response.results if r.matched_entities
                ],
                "citations": list(set(r.document_title for r in response.results if r.document_title)),
                "vector_hits": response.vector_hits,
                "graph_hits": response.graph_hits,
                "terms": response.terms,
                "error": None,
            }
        except Exception as e:
            return {"error": f"Retrieval failed: {str(e)}", "retrieved_results": []}

    return retrieve_node

def create_generate_node():
    """Creates the generate node that calls OpenRouter to produce an answer."""

    SYSTEM_PROMPT = """You are an enterprise knowledge assistant. Your task is to answer questions based ONLY on the provided context.

RULES:
1. Answer ONLY using information from the provided chunks. Do not invent information.
2. Always cite your sources by document title.
3. If the graph evidence shows relationships between entities, mention them explicitly.
4. If you cannot find a clear answer, say "I don't have enough information to answer this question accurately."
5. Be concise but thorough.
6. Your response MUST be a valid JSON object with the following structure:
{
  "answer": "Your complete answer text here with inline citations like [Document Title].",
  "confidence": 0.95,
  "reasoning": "Brief explanation of why you gave this answer based on the evidence."
}"""

    def generate_node(state: GraphRAGState) -> Dict[str, Any]:
        """Generate an answer using the LLM based on retrieved context."""
        if state.get("error"):
            return {
                "generated_answer": "An error occurred during retrieval.",
                "confidence": 0.0,
                "reasoning": state["error"],
            }

        if not state.get("retrieved_results"):
            return {
                "generated_answer": "I don't have enough information to answer this question.",
                "confidence": 0.0,
                "reasoning": "No relevant chunks found in the knowledge base.",
            }

        # Build context from retrieved results
        context_parts = []
        for i, result in enumerate(state["retrieved_results"], 1):
            chunk_content = result.get("content", "")
            doc_title = result.get("document_title", "Unknown")
            rrf_score = result.get("rrf_score", 0)
            matched_entities = result.get("matched_entities", [])

            context_parts.append(
                f"[Source {i}: {doc_title} | Relevance: {rrf_score:.3f}]\n"
                f"{chunk_content}\n"
                f"Graph Entities: {', '.join(matched_entities) if matched_entities else 'None'}"
            )

        context = "\n\n---\n\n".join(context_parts)

        # Build graph evidence summary
        graph_evidence_text = ""
        if state.get("graph_evidence"):
            evidence_lines = []
            for evidence in state["graph_evidence"]:
                entities = evidence.get("matched_entities", [])
                if entities:
                    evidence_lines.append(f"  - Entities found: {', '.join(entities)}")
            if evidence_lines:
                graph_evidence_text = "\n\nGraph Evidence:\n" + "\n".join(evidence_lines)

        user_prompt = f"""Question: {state['query']}

Retrieved Context:
{context}
{graph_evidence_text}

Please provide a complete answer based ONLY on the context above. Include citations by document title."""

        try:
            llm_response = call_llm(SYSTEM_PROMPT, user_prompt)

            return {
                "generated_answer": llm_response.get("answer", "No answer generated."),
                "confidence": float(llm_response.get("confidence", 0.5)),
                "reasoning": llm_response.get("reasoning", "No reasoning provided."),
            }
        except Exception as e:
            return {
                "generated_answer": "Failed to generate an answer.",
                "confidence": 0.0,
                "reasoning": f"LLM call failed: {str(e)}",
            }

    return generate_node




def create_feedback_node(feedback_service: FeedbackService):
    """Creates the feedback node that processes user feedback."""

    def feedback_node(state: GraphRAGState) -> GraphRAGState:
        """Process and store user feedback (if provided)."""
        # Feedback is handled separately via a dedicated endpoint
        # This node is a placeholder for future inline feedback processing
        return {
            **state,
            "feedback_submitted": False,
            "feedback_id": None,
        }

    return feedback_node

def create_save_interaction_node(repository):
    def save_interaction_node(state: GraphRAGState) -> Dict[str, Any]:
        if state.get("error") or not state.get("retrieved_results"):
            return {}

        # Get the ID. If LangGraph dropped it, we generate a fallback but LOG IT.
        interaction_id = state.get("interaction_id")
        if not interaction_id:
            print("⚠️ WARNING: LangGraph dropped interaction_id from state! Generating fallback ID.")
            interaction_id = str(uuid.uuid4())
            
        print(f"💾 Attempting to save interaction {interaction_id} to Neo4j...")

        chunk_ids = [r.get("chunk_id") for r in state.get("retrieved_results", []) if r.get("chunk_id")]
        
        entity_names = []
        for r in state.get("retrieved_results", []):
            entity_names.extend(r.get("matched_entities", []))
        entity_names = list(set(entity_names))
        
        document_titles = list(set(state.get("citations", [])))

        try:
            repository.save_interaction(
                interaction_id=interaction_id,
                query=state.get("query", ""),
                answer=state.get("generated_answer", ""),
                user_id=state.get("user_id"),
                chunk_ids=chunk_ids,
                entity_names=entity_names,
                document_titles=document_titles,
            )
            print(f"✅ Successfully saved interaction {interaction_id}")
        except Exception as e:
            print(f"❌ FAILED to save interaction {interaction_id}: {e}")
            
        return {}

    return save_interaction_node

def should_generate(state: GraphRAGState) -> str:
    """Conditional edge: only generate if retrieval succeeded."""
    if state.get("error") or not state.get("retrieved_results"):
        return END
    return "generate"


def build_graphrag_agent(
    retrieval_service: RetrievalService,
    feedback_service: FeedbackService,
) -> StateGraph:
    """Build and compile the LangGraph agent."""

    workflow = StateGraph(GraphRAGState)

    # 1. Add nodes
    workflow.add_node("retrieve", create_retrieve_node(retrieval_service))
    workflow.add_node("generate", create_generate_node())
    
    # FIX HERE: Actually add the save_interaction node to the graph!
    # We pass retrieval_service.repository so it has access to the Neo4j driver
    workflow.add_node("save_interaction", create_save_interaction_node(retrieval_service.repository))

    # Set entry point
    workflow.set_entry_point("retrieve")

    # 2. Add edges
    workflow.add_conditional_edges(
        "retrieve", 
        should_generate, 
        {"generate": "generate", END: END}
    )
    
    # FIX HERE: Route to save_interaction instead of process_feedback
    workflow.add_edge("generate", "save_interaction")
    workflow.add_edge("save_interaction", END)

    return workflow.compile()