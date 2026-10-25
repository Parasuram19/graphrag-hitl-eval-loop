import pytest
from fastapi import HTTPException
from unittest.mock import MagicMock
from app.services.feedback_service import FeedbackService
from app.schemas.feedback import FeedbackRequest, FeedbackType

def test_submit_feedback_raises_404_if_interaction_not_found():
    """Validates our ValueError -> HTTPException 404 error handling."""
    mock_repo = MagicMock()
    mock_repo.store_feedback_by_interaction.side_effect = ValueError(
        "Interaction ID 'fake-id' not found in database."
    )
    
    service = FeedbackService(repository=mock_repo)
    
    payload = FeedbackRequest(
        interaction_id="fake-id",
        feedback_type=FeedbackType.INCORRECT,
        rating=-1,
        comment="bad answer"
    )
    
    with pytest.raises(HTTPException) as exc_info:
        service.submit_feedback(payload)
        
    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()