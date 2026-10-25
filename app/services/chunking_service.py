from app.config import Settings


class ChunkingService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def split_text(self, text: str) -> list[str]:
        normalized = " ".join((text or "").split())
        if not normalized:
            return []

        size = max(50, self.settings.chunk_size)
        overlap = max(0, min(self.settings.chunk_overlap, size // 2))
        step = max(1, size - overlap)

        chunks = []
        for start in range(0, len(normalized), step):
            chunk = normalized[start:start + size].strip()
            if chunk:
                chunks.append(chunk)
            if start + size >= len(normalized):
                break

        return chunks