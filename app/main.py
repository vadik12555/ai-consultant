"""Точка входа: собираем зависимости, индексируем документы, запускаем бота."""

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeChat

from app.bot import booking, client, manager, menu
from app.config import get_settings
from app.db.repositories import (
    BookingRepository,
    DocumentRepository,
    LeadRepository,
    PgChunkSearcher,
    QuestionRepository,
    StatsRepository,
)
from app.db.session import make_session_factory
from app.llm.ollama import OllamaClient
from app.services.booking import BookingService
from app.services.catalog import load_catalog
from app.services.indexer import IndexerService
from app.services.leads import LeadService
from app.services.qa import QAService

logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    settings = get_settings()

    engine, sessions = make_session_factory(settings.database_url)
    ollama = OllamaClient(settings.ollama_url, settings.llm_model, settings.embed_model)

    lead_repository = LeadRepository(sessions)
    question_repository = QuestionRepository(sessions)
    booking_repository = BookingRepository(sessions)
    indexer = IndexerService(
        DocumentRepository(sessions),
        ollama,
        settings.docs_dir,
        settings.chunk_size,
        settings.chunk_overlap,
    )
    qa_service = QAService(
        embedder=ollama,
        llm=ollama,
        searcher=PgChunkSearcher(sessions),
        questions=question_repository,
        company_name=settings.company_name,
        top_k=settings.top_k,
        min_score=settings.min_score,
    )

    report = await indexer.sync()
    logger.info(
        "Индексация: новых/изменённых %d, без изменений %d, удалено %d, чанков %d",
        report.indexed,
        report.skipped,
        report.removed,
        report.chunks,
    )

    bot = Bot(settings.telegram_bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    # Всё, что положили в Dispatcher, aiogram передаёт в хендлеры по имени аргумента
    dp = Dispatcher(
        qa_service=qa_service,
        lead_service=LeadService(lead_repository),
        lead_repository=lead_repository,
        question_repository=question_repository,
        indexer=indexer,
        manager_chat_id=settings.manager_chat_id,
        company_name=settings.company_name,
        catalog=load_catalog(settings.docs_dir),
        booking_service=BookingService(booking_repository),
        booking_repository=booking_repository,
        stats_repository=StatsRepository(sessions),
    )
    is_manager = F.chat.id == settings.manager_chat_id
    manager.router.message.filter(is_manager)
    manager.router.callback_query.filter(F.message.chat.id == settings.manager_chat_id)
    # Порядок важен: команды менеджера → запись → кнопки меню → свободный вопрос (ловит любой текст)
    dp.include_routers(manager.router, booking.router, menu.router, client.router)

    await bot.set_my_commands([BotCommand(command="start", description="Начать")])
    await bot.set_my_commands(
        [
            BotCommand(command="leads", description="Новые заявки"),
            BotCommand(command="bookings", description="Ближайшие записи"),
            BotCommand(command="stats", description="Статистика за неделю"),
            BotCommand(command="unanswered", description="Вопросы без ответа"),
            BotCommand(command="reload", description="Переиндексировать документы"),
        ],
        scope=BotCommandScopeChat(chat_id=settings.manager_chat_id),
    )

    try:
        logger.info("Бот запущен")
        await dp.start_polling(bot)
    finally:
        await ollama.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
