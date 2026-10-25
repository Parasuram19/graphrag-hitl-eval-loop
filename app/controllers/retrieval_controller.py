class RetrievalController:
    def __init__(self, service):
        self.service = service

    def retrieve(self, payload):
        return self.service.retrieve(payload)