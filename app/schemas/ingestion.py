from typing import Any, Optional

from pydantic import BaseModel, Field


class EntityIn(BaseModel):
    name: str
    kind: Optional[str] = None


class RelationshipIn(BaseModel):
    source: str
    target: str
    type: str


class IngestDocumentRequest(BaseModel):
    id: Optional[str] = None
    title: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    allowed_roles: list[str] = Field(default_factory=list)
    entities: list[EntityIn] = Field(default_factory=list)
    relationships: list[RelationshipIn] = Field(default_factory=list)


class IngestDocumentResponse(BaseModel):
    document_id: str
    status: str
    chunks_created: int
    entities_created: int
    relationships_created: int
    vector_index: str