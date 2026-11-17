import httpx


class OllamaClient:
    """Работа с локальной Ollama по HTTP. Реализует и Embedder, и LLM."""

    def __init__(self, base_url: str, llm_model: str, embed_model: str) -> None:
        self._http = httpx.AsyncClient(base_url=base_url, timeout=180)
        self._llm_model = llm_model
        self._embed_model = embed_model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._http.post(
            "/api/embed", json={"model": self._embed_model, "input": texts, "keep_alive": "1m"}
        )
        response.raise_for_status()
        return response.json()["embeddings"]

    async def generate(self, system: str, user: str) -> str:
        response = await self._http.post(
            "/api/chat",
            json={
                "model": self._llm_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "keep_alive": "1m",  # выгрузить модель из RAM через минуту простоя
                "options": {"temperature": 0.1},  # меньше фантазии — больше точности
            },
        )
        response.raise_for_status()
        return response.json()["message"]["content"].strip()

    async def close(self) -> None:
        await self._http.aclose()
