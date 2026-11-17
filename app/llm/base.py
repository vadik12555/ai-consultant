from typing import Protocol


class Embedder(Protocol):
    """Превращает тексты в векторы (списки чисел), чтобы искать похожие по смыслу."""

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class LLM(Protocol):
    """Генерирует ответ по системной инструкции и сообщению пользователя."""

    async def generate(self, system: str, user: str) -> str: ...
