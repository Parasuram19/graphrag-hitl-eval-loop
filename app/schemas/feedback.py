from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum

class FeedbackType(str, Enum):
    CORRECT = "CORRECT"
    INCORRECT = "INCORRECT"
    MISSING_SOURCE = "MISSING_SOURCE"
    WRONG_ENTITY = "WRONG_ENTITY"
    WRONG_RELATIONSHIP = "WRONG_RELATIONSHIP"
    OUTDATED_INFORMATION = "OUTDATED_INFORMATION"
    TOO_VAGUE = "TOO_VAGUE"
    ACCESS_ISSUE = "ACCESS_ISSUE"
    USER_PROVIDED_CORRECTION = "USER_PROVIDED_CORRECTION"

class FeedbackRequest(BaseModel):
    interaction_id: str
    feedback_type: FeedbackType
    rating: int = Field(ge=-1, le=1)
    comment: Optional[str] = None
    user_id: Optional[str] = None

class FeedbackResponse(BaseModel):
    feedback_id: str
    status: str