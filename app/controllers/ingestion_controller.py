class IngestionController:
    def __init__(self, service):
        self.service = service

    def ingest_document(self, payload):
        return self.service.ingest_document(payload)