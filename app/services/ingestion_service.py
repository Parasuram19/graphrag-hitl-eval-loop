import json
import re
from uuid import uuid4

from app.config import Settings
from app.schemas.ingestion import IngestDocumentRequest, IngestDocumentResponse
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.graph_extraction_service import GraphExtractionService


class IngestionService:
    def __init__(
        self,
        repository,
        chunking_service: ChunkingService,
        embedding_service: EmbeddingService,
        graph_extraction_service: GraphExtractionService,
        settings: Settings,
    ):
        self.repository = repository
        self.chunking_service = chunking_service
        self.embedding_service = embedding_service
        self.graph_extraction_service = graph_extraction_service
        self.settings = settings

    def ingest_document(self, payload: IngestDocumentRequest) -> IngestDocumentResponse:
        document_id = payload.id or str(uuid4())

        chunk_texts = self.chunking_service.split_text(payload.content)

        chunks = []
        for index, text in enumerate(chunk_texts):
            chunks.append(
                {
                    "id": f"{document_id}:chunk:{index}",
                    "content": text,
                    "index": index,
                    "embedding": self.embedding_service.embed_text(text),
                }
            )

        entities = self.graph_extraction_service.extract_entities_for_chunks(
            chunks=chunks,
            supplied_entities=payload.entities,
        )

        relationships = self._normalize_relationships(payload.relationships)
        self._ensure_relationship_entities(entities, relationships)

        metadata_json = json.dumps(payload.metadata or {})

        self.repository.save_document(
            document_id=document_id,
            title=payload.title,
            metadata_json=metadata_json,
            allowed_roles=payload.allowed_roles,
            chunks=chunks,
            entities=entities,
            relationships=relationships,
        )

        return IngestDocumentResponse(
            document_id=document_id,
            status="ingested",
            chunks_created=len(chunks),
            entities_created=len(entities),
            relationships_created=len(relationships),
            vector_index=self.settings.vector_index_name,
        )

    def _normalize_relationships(self, relationships):
        normalized = []

        for relationship in relationships or []:
            source = self.graph_extraction_service.normalize_entity_name(
                relationship.source
            )
            target = self.graph_extraction_service.normalize_entity_name(
                relationship.target
            )
            rel_type = self._normalize_relationship_type(relationship.type)

            if source and target and rel_type:
                normalized.append(
                    {
                        "source": source,
                        "target": target,
                        "type": rel_type,
                    }
                )

        return normalized

    def _normalize_relationship_type(self, value: str) -> str | None:
        value = re.sub(
            r"[^A-Za-z0-9_]+",
            "_",
            (value or "").strip().upper(),
        )
        value = re.sub(r"_+", "_", value).strip("_")

        if not value or not re.fullmatch(r"[A-Z][A-Z0-9_]*", value):
            return None

        return value

    def _ensure_relationship_entities(self, entities, relationships):
        existing_names = {entity["name"] for entity in entities}

        for relationship in relationships:
            for name in (relationship["source"], relationship["target"]):
                if name not in existing_names:
                    entities.append(
                        {
                            "name": name,
                            "kind": None,
                            "chunk_ids": [],
                        }
                    )
                    existing_names.add(name)