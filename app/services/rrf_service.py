from typing import Any, Dict, List


class RRFService:
    def fuse(
        self,
        vector_hits: List[Dict[str, Any]],
        graph_hits: List[Dict[str, Any]],
        k: int = 60,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        vector_sorted = sorted(
            vector_hits,
            key=lambda x: float(x.get("score") or 0.0),
            reverse=True,
        )

        graph_sorted = sorted(
            graph_hits,
            key=lambda x: float(x.get("score") or 0.0),
            reverse=True,
        )

        fused: Dict[str, Dict[str, Any]] = {}

        for rank, hit in enumerate(vector_sorted, start=1):
            chunk_id = str(hit.get("chunk_id"))
            item = fused.setdefault(chunk_id, self._base(hit))
            item["rrf_score"] += 1.0 / (k + rank)
            item["vector_rank"] = rank
            item["vector_score"] = float(hit.get("score") or 0.0)

        for rank, hit in enumerate(graph_sorted, start=1):
            chunk_id = str(hit.get("chunk_id"))
            item = fused.setdefault(chunk_id, self._base(hit))
            item["rrf_score"] += 1.0 / (k + rank)
            item["graph_rank"] = rank
            item["graph_score"] = float(hit.get("score") or 0.0)

            if hit.get("matched_entities"):
                merged_entities = (
                    item.get("matched_entities", []) + hit.get("matched_entities", [])
                )
                item["matched_entities"] = list(dict.fromkeys(merged_entities))

        results = sorted(
            fused.values(),
            key=lambda x: x["rrf_score"],
            reverse=True,
        )

        return results[:limit]

    def _base(self, hit: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "chunk_id": str(hit.get("chunk_id")),
            "content": hit.get("content") or "",
            "document_title": hit.get("document_title"),
            "rrf_score": 0.0,
            "vector_score": None,
            "graph_score": None,
            "vector_rank": None,
            "graph_rank": None,
            "matched_entities": hit.get("matched_entities") or [],
        }