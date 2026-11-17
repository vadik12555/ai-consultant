"""Весь SQL проекта живёт здесь. Сервисы работают с этими классами, а не с сессией напрямую."""

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Chunk, Document, Lead, LeadStatus, UnansweredQuestion
from app.rag.types import FoundChunk


class DocumentRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._sessions = session_factory

    async def get_hashes(self) -> dict[str, str]:
        async with self._sessions() as session:
            rows = await session.execute(select(Document.filename, Document.sha256))
            return dict(rows.tuples().all())

    async def replace(
        self, filename: str, sha256: str, texts: list[str], embeddings: list[list[float]]
    ) -> None:
        """Удаляет старую версию документа и сохраняет новую — в одной транзакции."""
        async with self._sessions.begin() as session:
            await session.execute(delete(Document).where(Document.filename == filename))
            document = Document(filename=filename, sha256=sha256)
            document.chunks = [
                Chunk(position=i, text=text, embedding=vector)
                for i, (text, vector) in enumerate(zip(texts, embeddings, strict=True))
            ]
            session.add(document)

    async def delete_missing(self, existing_filenames: set[str]) -> int:
        """Удаляет из БД документы, файлов которых больше нет в папке."""
        async with self._sessions.begin() as session:
            result = await session.execute(
                delete(Document).where(Document.filename.not_in(existing_filenames))
            )
            return result.rowcount


class PgChunkSearcher:
    """Поиск ближайших кусков по косинусному расстоянию средствами pgvector."""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._sessions = session_factory

    async def search(self, embedding: list[float], top_k: int) -> list[FoundChunk]:
        distance = Chunk.embedding.cosine_distance(embedding)
        query = (
            select(Chunk.text, Document.filename, distance.label("distance"))
            .join(Document)
            .order_by(distance)
            .limit(top_k)
        )
        async with self._sessions() as session:
            rows = await session.execute(query)
            return [
                FoundChunk(text=text, source=filename, score=1 - dist)
                for text, filename, dist in rows.tuples()
            ]


class LeadRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._sessions = session_factory

    async def add(
        self, telegram_user_id: int, name: str, phone: str, question: str | None
    ) -> Lead:
        async with self._sessions.begin() as session:
            lead = Lead(
                telegram_user_id=telegram_user_id, name=name, phone=phone, question=question
            )
            session.add(lead)
        return lead

    async def list_new(self, limit: int = 20) -> list[Lead]:
        async with self._sessions() as session:
            rows = await session.scalars(
                select(Lead)
                .where(Lead.status == LeadStatus.NEW)
                .order_by(Lead.created_at)
                .limit(limit)
            )
            return list(rows)

    async def mark_done(self, lead_id: int) -> None:
        async with self._sessions.begin() as session:
            await session.execute(
                update(Lead).where(Lead.id == lead_id).values(status=LeadStatus.DONE)
            )


class UnansweredRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._sessions = session_factory

    async def add(self, telegram_user_id: int, question: str) -> None:
        async with self._sessions.begin() as session:
            session.add(UnansweredQuestion(telegram_user_id=telegram_user_id, question=question))

    async def list_recent(self, limit: int = 20) -> list[UnansweredQuestion]:
        async with self._sessions() as session:
            rows = await session.scalars(
                select(UnansweredQuestion)
                .order_by(UnansweredQuestion.created_at.desc())
                .limit(limit)
            )
            return list(rows)
