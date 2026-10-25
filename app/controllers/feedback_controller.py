class FeedbackController:
    def __init__(self, service):
        self.service = service

    def submit_feedback(self, payload):
        return self.service.submit_feedback(payload)

    def get_feedback_for_entity(self, entity_name: str):
        return self.service.get_feedback_for_entity(entity_name)

    def get_negative_feedback_summary(self):
        return self.service.get_negative_feedback_summary()