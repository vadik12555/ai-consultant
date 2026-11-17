from dataclasses import dataclass, field
from typing import Protocol

from app.llm.base import LLM, Embedder
from app.rag.prompt import NO_ANSWER_MARKER, build_system_prompt, build_user_prompt
from app.rag.types import ChunkSearcher, FoundChunk


class QuestionLog(Protocol):
    """Журнал вопросов: нужен для /unanswered и /stats."""

    async def add(self, telegram_user_id: int, question: str, answered: bool) -> None: ...


@dataclass
class Answer:
    text: str | None  # None — в документах ответа нет
    sources: list[str] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return self.text is not None


class QAService:
    """Ответ на вопрос клиента: вектор вопроса → поиск кусков → проверка релевантности → LLM."""

    def __init__(
        self,
        embedder: Embedder,
        llm: LLM,
        searcher: ChunkSearcher,
        questions: QuestionLog,
        company_name: str,
        top_k: int = 5,
        min_score: float = 0.5,
    ) -> None:
        self._embedder = embedder
        self._llm = llm
        self._searcher = searcher
        self._questions = questions
        self._system_prompt = build_system_prompt(company_name)
        self._top_k = top_k
        self._min_score = min_score

    async def find_relevant(self, question: str) -> list[FoundChunk]:
        """Топ-k кусков, похожих на вопрос не меньше min_score."""
        [vector] = await self._embedder.embed([question])
        chunks = await self._searcher.search(vector, self._top_k)
        return [chunk for chunk in chunks if chunk.score >= self._min_score]

    async def answer(self, telegram_user_id: int, question: str) -> Answer:
        chunks = await self.find_relevant(question)
        if chunks:
            text = await self._llm.generate(
                self._system_prompt, build_user_prompt(question, chunks)
            )
            if NO_ANSWER_MARKER not in text:
                sources = list(dict.fromkeys(chunk.source for chunk in chunks))
                await self._questions.add(telegram_user_id, question, answered=True)
                return Answer(text=text, sources=sources)

        # Сюда попадаем, если ничего похожего не нашли или LLM сказала, что ответа нет
        await self._questions.add(telegram_user_id, question, answered=False)
        return Answer(text=None)
