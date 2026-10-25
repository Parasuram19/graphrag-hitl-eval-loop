import re
from typing import List

from app.config import Settings
from app.schemas.retrieval import RetrievalRequest, RetrievalResponse, RetrievalResult
from app.services.embedding_service import EmbeddingService
from app.services.rrf_service import RRFService


STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "into", "are",
    "was", "were", "will", "which", "what", "who", "whom", "when", "where",
    "why", "how", "does", "do", "did", "can", "could", "should", "would",
    "please", "show", "give", "tell", "about", "your", "our", "you",
}


class RetrievalService:
    def __init__(
        self,
        repository,
        embedding_service: EmbeddingService,
        rrf_service: RRFService,
        settings: Settings,
    ):
        self.repository = repository
        self.embedding_service = embedding_service
        self.rrf_service = rrf_service
        self.settings = settings

    def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        top_k = request.top_k or self.settings.default_top_k
        top_k = max(1, min(top_k, self.settings.max_top_k))

        query_embedding = self.embedding_service.embed_query(request.query)

        # Pass user roles for ACL filtering
        vector_hits = self.repository.vector_search(
            embedding=query_embedding,
            limit=top_k * 2,
            user_roles=request.user_roles,
        )

        terms = self._extract_terms(request.query)

        graph_hits = self.repository.graph_search(
            terms=terms,
            limit=top_k * 2,
            user_roles=request.user_roles,
        )

        fused = self.rrf_service.fuse(
            vector_hits=vector_hits,
            graph_hits=graph_hits,
            k=self.settings.rrf_k,
            limit=top_k,
        )

        results = [RetrievalResult(**item) for item in fused]

        # Build citations
        citations = list(set([
            r.document_title for r in results if r.document_title
        ]))

        # Build graph evidence
        graph_evidence = [
            {
                "chunk_id": r.chunk_id,
                "matched_entities": r.matched_entities,
            }
            for r in results if r.matched_entities
        ]

        # Generate simple answer (fallback without LLM)
        answer = self._generate_answer(fused)

        return RetrievalResponse(
            query=request.query,
            answer=answer,
            results=results,
            graph_evidence=graph_evidence,
            vector_hits=len(vector_hits),
            graph_hits=len(graph_hits),
            terms=terms,
            citations=citations,
        )

    def _generate_answer(self, fused_results) -> str:
        """Simple answer generation from top results (no LLM)."""
        if not fused_results:
            return "No relevant information found."
        
        top_result = fused_results[0]
        content = top_result.get("content", "")
        entities = top_result.get("matched_entities", [])
        
        answer = content[:500]  # Take first 500 chars
        if entities:
            answer += f"\n\nRelated entities: {', '.join(entities)}"
        
        return answer

    def _extract_terms(self, text: str) -> List[str]:
        tokens = re.findall(r"[a-z0-9]+", (text or "").lower())

        return [
            token
            for token in tokens
            if len(token) > 1 and token not in STOPWORDS
        ]