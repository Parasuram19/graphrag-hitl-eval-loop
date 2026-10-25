from fastapi import APIRouter, Depends

from app.controllers.retrieval_controller import RetrievalController
from app.dependencies import get_retrieval_controller
from app.schemas.retrieval import RetrievalRequest, RetrievalResponse


router = APIRouter(prefix="/api/v1", tags=["Retrieval"])


@router.post("/retrieve", response_model=RetrievalResponse)
def retrieve(
    payload: RetrievalRequest,
    controller: RetrievalController = Depends(get_retrieval_controller),
):
    return controller.retrieve(payload)