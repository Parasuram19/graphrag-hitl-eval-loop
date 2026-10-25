import re
from typing import List, Optional

from app.schemas.ingestion import EntityIn


STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "into", "are",
    "was", "were", "will", "your", "you", "our", "policy", "policies",
    "team", "teams", "document", "documents", "section", "version",
    "data", "retention", "security"
}


class GraphExtractionService:
    capitalized_phrase = re.compile(
        r"\b[A-Z][A-Za-z0-9&\-']+(?:\s+[A-Z][A-Za-z0-9&\-']+)+\b"
    )
    capitalized_single = re.compile(
        r"\b[A-Z][A-Za-z0-9&\-']{2,}\b"
    )

    def normalize_entity_name(self, name: str) -> str:
        return " ".join((name or "").split()).strip()

    def extract_entities_for_chunks(
        self,
        chunks: List[dict],
        supplied_entities: List[EntityIn],
    ) -> List[dict]:
        entity_map = {}

        if supplied_entities:
            for entity in supplied_entities:
                name = self.normalize_entity_name(entity.name)
                if not name:
                    continue

                entity_map.setdefault(
                    name,
                    {
                        "name": name,
                        "kind": entity.kind,
                        "chunk_ids": [],
                    },
                )

            for chunk in chunks:
                content_lower = chunk.get("content", "").lower()
                chunk_id = chunk.get("id")

                for name, entity in entity_map.items():
                    if name.lower() in content_lower and chunk_id not in entity["chunk_ids"]:
                        entity["chunk_ids"].append(chunk_id)

            # Workability fallback:
            # If a supplied entity is not found in text, attach it to all chunks.
            # This keeps explicit graph entities searchable.
            for entity in entity_map.values():
                if not entity["chunk_ids"]:
                    entity["chunk_ids"] = [
                        chunk.get("id")
                        for chunk in chunks
                        if chunk.get("id")
                    ]

            return list(entity_map.values())

        for chunk in chunks:
            content = chunk.get("content", "")
            chunk_id = chunk.get("id")

            for name in self._extract_from_text(content):
                entity = entity_map.setdefault(
                    name,
                    {
                        "name": name,
                        "kind": None,
                        "chunk_ids": [],
                    },
                )

                if chunk_id not in entity["chunk_ids"]:
                    entity["chunk_ids"].append(chunk_id)

        return list(entity_map.values())

    def _extract_from_text(self, text: str) -> List[str]:
        names = []

        for match in self.capitalized_phrase.findall(text or ""):
            name = self._clean(match)
            if name:
                names.append(name)

        for match in self.capitalized_single.findall(text or ""):
            name = self._clean(match)
            if name and name.lower() not in STOPWORDS:
                names.append(name)

        return list(dict.fromkeys(names))

    def _clean(self, name: str) -> Optional[str]:
        name = self.normalize_entity_name(name)
        if not name:
            return None

        if name.lower() in STOPWORDS:
            return None

        return name