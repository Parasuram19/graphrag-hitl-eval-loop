from typing import Optional

from pydantic import BaseModel, Field


class RetrievalRequest(BaseModel):
    query: str
    top_k: Optional[int] = None
    user_id: Optional[str] = None
    user_roles: list[str] = Field(default_factory=list)


class RetrievalResult(BaseModel):
    chunk_id: str
    content: str
    document_title: Optional[str] = None
    rrf_score: float
    vector_score: Optional[float] = None
    graph_score: Optional[float] = None
    vector_rank: Optional[int] = None
    graph_rank: Optional[int] = None
    matched_entities: list[str] = Field(default_factory=list)


class RetrievalResponse(BaseModel):
    query: str
    answer: Optional[str] = None
    results: list[RetrievalResult]
    graph_evidence: list[dict] = Field(default_factory=list)
    vector_hits: int
    graph_hits: int
    terms: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)