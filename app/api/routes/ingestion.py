from fastapi import APIRouter, Depends

from app.controllers.ingestion_controller import IngestionController
from app.dependencies import get_ingestion_controller
from app.schemas.ingestion import IngestDocumentRequest, IngestDocumentResponse


router = APIRouter(prefix="/api/v1/ingest", tags=["Ingestion"])


@router.post("/document", response_model=IngestDocumentResponse)
def ingest_document(
    payload: IngestDocumentRequest,
    controller: IngestionController = Depends(get_ingestion_controller),
):
    return controller.ingest_document(payload)