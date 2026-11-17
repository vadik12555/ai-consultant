"""Весь SQL проекта живёт здесь. Сервисы работают с этими классами, а не с сессией напрямую."""

from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Booking, BookingStatus, Chunk, Document, Lead, LeadStatus, Question
from app.rag.types import FoundChunk
from app.services.booking import SlotTakenError
from app.services.stats import WeekStats


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

    async def add(self, telegram_user_id: int, name: str, phone: str, question: str | None) -> Lead:
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


class QuestionRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._sessions = session_factory

    async def add(self, telegram_user_id: int, question: str, answered: bool) -> None:
        async with self._sessions.begin() as session:
            session.add(
                Question(telegram_user_id=telegram_user_id, question=question, answered=answered)
            )

    async def list_unanswered(self, limit: int = 20) -> list[Question]:
        async with self._sessions() as session:
            rows = await session.scalars(
                select(Question)
                .where(Question.answered.is_(False))
                .order_by(Question.created_at.desc())
                .limit(limit)
            )
            return list(rows)


class BookingRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._sessions = session_factory

    async def busy_slots(self, start: datetime, end: datetime) -> set[datetime]:
        async with self._sessions() as session:
            rows = await session.scalars(
                select(Booking.starts_at).where(
                    Booking.status == BookingStatus.ACTIVE,
                    Booking.starts_at >= start,
                    Booking.starts_at < end,
                )
            )
            return set(rows)

    async def add(
        self, telegram_user_id: int, name: str, phone: str, service: str, starts_at: datetime
    ) -> Booking:
        booking = Booking(
            telegram_user_id=telegram_user_id,
            name=name,
            phone=phone,
            service=service,
            starts_at=starts_at,
        )
        try:
            async with self._sessions.begin() as session:
                session.add(booking)
        except IntegrityError as error:  # сработал уникальный индекс — слот только что заняли
            raise SlotTakenError(starts_at) from error
        return booking

    async def list_upcoming(self, now: datetime, limit: int = 30) -> list[Booking]:
        async with self._sessions() as session:
            rows = await session.scalars(
                select(Booking)
                .where(Booking.status == BookingStatus.ACTIVE, Booking.starts_at >= now)
                .order_by(Booking.starts_at)
                .limit(limit)
            )
            return list(rows)


class StatsRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._sessions = session_factory

    async def collect(self, since: datetime) -> WeekStats:
        async with self._sessions() as session:
            questions = await session.scalar(
                select(func.count()).select_from(Question).where(Question.created_at >= since)
            )
            unanswered = await session.scalar(
                select(func.count())
                .select_from(Question)
                .where(Question.created_at >= since, Question.answered.is_(False))
            )
            leads = await session.scalar(
                select(func.count()).select_from(Lead).where(Lead.created_at >= since)
            )
            bookings = await session.scalar(
                select(func.count()).select_from(Booking).where(Booking.created_at >= since)
            )
            top_services = await session.execute(
                select(Booking.service, func.count().label("n"))
                .where(Booking.created_at >= since)
                .group_by(Booking.service)
                .order_by(func.count().desc())
                .limit(3)
            )
            top_unanswered = await session.scalars(
                select(Question.question)
                .where(Question.created_at >= since, Question.answered.is_(False))
                .group_by(Question.question)
                .order_by(func.count().desc())
                .limit(5)
            )
            return WeekStats(
                questions=questions or 0,
                unanswered=unanswered or 0,
                leads=leads or 0,
                bookings=bookings or 0,
                top_services=[(name, count) for name, count in top_services.tuples()],
                top_unanswered=list(top_unanswered),
            )
