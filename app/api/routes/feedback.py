from fastapi import APIRouter, Depends

from app.controllers.feedback_controller import FeedbackController
from app.dependencies import get_feedback_controller
from app.schemas.feedback import FeedbackRequest, FeedbackResponse


router = APIRouter(prefix="/api/v1/feedback", tags=["Feedback"])


@router.post("/submit", response_model=FeedbackResponse)
def submit_feedback(
    payload: FeedbackRequest,
    controller: FeedbackController = Depends(get_feedback_controller),
):
    return controller.submit_feedback(payload)


@router.get("/entity/{entity_name}")
def get_entity_feedback(
    entity_name: str,
    controller: FeedbackController = Depends(get_feedback_controller),
):
    return controller.get_feedback_for_entity(entity_name)


@router.get("/negative-summary")
def get_negative_summary(
    controller: FeedbackController = Depends(get_feedback_controller),
):
    return controller.get_negative_feedback_summary()