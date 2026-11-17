from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class FoundChunk:
    text: str
    source: str  # имя файла
    score: float  # косинусная похожесть: 1 — то же самое, 0 — ничего общего


class ChunkSearcher(Protocol):
    async def search(self, embedding: list[float], top_k: int) -> list[FoundChunk]: ...
