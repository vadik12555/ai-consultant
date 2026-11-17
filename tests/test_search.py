"""Тесты поиска и логики «отвечать / честно сказать, что ответа нет».

Вместо Postgres и Ollama используем in-memory поиск и FakeEmbedder/FakeLLM — тесты быстрые и без сети.
"""

import math

from app.llm.fake import FakeEmbedder, FakeLLM
from app.rag.prompt import NO_ANSWER_MARKER
from app.rag.types import FoundChunk
from app.services.qa import QAService

DOCS = {
    "price.md": "Замена моторного масла и фильтра стоит 900 рублей",
    "faq.md": "График работы понедельник суббота с 8 до 20",
    "tires.md": "Сезонная смена колёс шиномонтаж 2000 рублей",
}


class InMemorySearcher:
    """Тот же контракт, что у PgChunkSearcher, но косинусная похожесть считается в Python."""

    def __init__(self, items: list[tuple[str, str, list[float]]]) -> None:
        self.items = items

    async def search(self, embedding: list[float], top_k: int) -> list[FoundChunk]:
        scored = [
            FoundChunk(text=text, source=source, score=_cosine(embedding, vector))
            for source, text, vector in self.items
        ]
        return sorted(scored, key=lambda c: c.score, reverse=True)[:top_k]


class InMemoryUnanswered:
    def __init__(self) -> None:
        self.questions: list[str] = []

    async def add(self, telegram_user_id: int, question: str) -> None:
        self.questions.append(question)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


async def make_service(llm_answer: str = "Замена масла — 900 рублей.", top_k: int = 5):
    embedder = FakeEmbedder()
    vectors = await embedder.embed(list(DOCS.values()))
    searcher = InMemorySearcher([(s, t, v) for (s, t), v in zip(DOCS.items(), vectors)])
    llm = FakeLLM(llm_answer)
    unanswered = InMemoryUnanswered()
    service = QAService(embedder, llm, searcher, unanswered, "Мотор", top_k=top_k, min_score=0.3)
    return service, llm, unanswered


async def test_most_similar_chunk_comes_first() -> None:
    service, _, _ = await make_service()
    chunks = await service.find_relevant("сколько стоит замена масла")
    assert chunks[0].source == "price.md"


async def test_top_k_limits_results() -> None:
    service, _, _ = await make_service(top_k=1)
    assert len(await service.find_relevant("стоит рублей")) == 1


async def test_irrelevant_question_is_filtered_out() -> None:
    service, _, _ = await make_service()
    assert await service.find_relevant("какая завтра погода") == []


async def test_answer_uses_found_chunks_and_returns_sources() -> None:
    service, llm, unanswered = await make_service()
    answer = await service.answer(1, "сколько стоит замена масла")

    assert answer.found
    assert "price.md" in answer.sources
    assert "900 рублей" in llm.calls[0][1]  # фрагмент документа попал в промпт
    assert unanswered.questions == []


async def test_no_relevant_chunks_means_no_llm_call_and_unanswered_saved() -> None:
    service, llm, unanswered = await make_service()
    answer = await service.answer(1, "какая завтра погода")

    assert not answer.found
    assert llm.calls == []  # LLM даже не вызывали — экономим время и не даём ей фантазировать
    assert unanswered.questions == ["какая завтра погода"]


async def test_llm_saying_no_answer_is_respected() -> None:
    service, _, unanswered = await make_service(llm_answer=NO_ANSWER_MARKER)
    answer = await service.answer(1, "сколько стоит замена масла на тракторе")

    assert not answer.found
    assert unanswered.questions == ["сколько стоит замена масла на тракторе"]
