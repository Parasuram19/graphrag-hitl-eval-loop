from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.controllers.agent_controller import AgentController
from app.dependencies import get_agent_controller
from app.schemas.feedback import FeedbackRequest, FeedbackResponse


class AgentQueryRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
    user_roles: list[str] = Field(default_factory=list)
    top_k: Optional[int] = None


router = APIRouter(prefix="/api/v1/agent", tags=["Agent"])


@router.post("/query")
def run_agent_query(
    payload: AgentQueryRequest,
    controller: AgentController = Depends(get_agent_controller),
):
    """
    Run the full GraphRAG agent pipeline:
    1. Retrieve (vector + graph + RRF with ACL)
    2. Generate answer using OpenRouter LLM
    """
    return controller.run_query(payload)


@router.post("/feedback", response_model=FeedbackResponse)
def submit_agent_feedback(
    payload: FeedbackRequest,
    controller: AgentController = Depends(get_agent_controller),
):
    """
    Submit feedback on a previously generated answer.
    Links feedback to chunks, entities, and documents in Neo4j.
    """
    return controller.submit_feedback(payload)