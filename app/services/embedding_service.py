import hashlib
import math
import re
from typing import List

from app.config import Settings

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None


class EmbeddingService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._model = None

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(text) for text in texts]

    def embed_text(self, text: str) -> List[float]:
        if self.settings.embedding_provider == "sentence_transformer":
            return self._embed_with_sentence_transformer(text)
        return self._deterministic_embedding(text)

    def embed_query(self, query: str) -> List[float]:
        return self.embed_text(query)

    def _embed_with_sentence_transformer(self, text: str) -> List[float]:
        if SentenceTransformer is None:
            raise RuntimeError(
                "sentence-transformers is not installed. "
                "Install it or set EMBEDDING_PROVIDER=deterministic."
            )

        if self._model is None:
            self._model = SentenceTransformer(
                self.settings.sentence_transformer_model
            )

        vector = self._model.encode(
            text,
            normalize_embeddings=True
        ).tolist()

        dim = self.settings.embedding_dimension
        if len(vector) < dim:
            vector.extend([0.0] * (dim - len(vector)))

        return vector[:dim]

    def _deterministic_embedding(self, text: str) -> List[float]:
        dim = self.settings.embedding_dimension
        vector = [0.0] * dim

        tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "little") % dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[idx] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector

        return [value / norm for value in vector]