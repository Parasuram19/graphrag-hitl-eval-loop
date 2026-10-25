class AgentController:
    def __init__(self, agent_service, feedback_controller):
        self.agent_service = agent_service
        self.feedback_controller = feedback_controller

    def run_query(self, payload):
        return self.agent_service.run_query(
            query=payload.query,
            user_id=payload.user_id,
            user_roles=payload.user_roles,
            top_k=payload.top_k,
        )

    def submit_feedback(self, payload):
        return self.feedback_controller.submit_feedback(payload)