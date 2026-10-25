from fastapi import HTTPException
from app.schemas.feedback import FeedbackRequest, FeedbackResponse

class FeedbackService:
    def __init__(self, repository):
        self.repository = repository

    def submit_feedback(self, payload: FeedbackRequest) -> FeedbackResponse:
        try:
            result = self.repository.store_feedback_by_interaction(
                interaction_id=payload.interaction_id,
                feedback_type=payload.feedback_type.value,
                rating=payload.rating,
                comment=payload.comment,
                user_id=payload.user_id,
            )
            return FeedbackResponse(
                feedback_id=result["feedback_id"],
                status=result["status"],
            )
        except ValueError as e:
            # Return a clean 404 error to the API client
            raise HTTPException(status_code=404, detail=str(e))

    

    def get_feedback_for_entity(self, entity_name: str):
        return self.repository.get_feedback_for_entity(entity_name)

    def get_negative_feedback_summary(self):
        return self.repository.get_negative_feedback_summary()