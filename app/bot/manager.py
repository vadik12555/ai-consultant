"""Команды менеджера. Работают только в чате MANAGER_CHAT_ID (фильтр вешается в main.py)."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import lead_done_button
from app.db.repositories import LeadRepository, UnansweredRepository
from app.services.catalog import Catalog, load_catalog
from app.services.indexer import IndexerService
from app.services.leads import format_lead

router = Router(name="manager")


@router.message(Command("leads"))
async def leads(message: Message, lead_repository: LeadRepository) -> None:
    new_leads = await lead_repository.list_new()
    if not new_leads:
        await message.answer("Новых заявок нет 👍")
        return
    for lead in new_leads:
        created = lead.created_at.strftime("%d.%m %H:%M")
        await message.answer(
            f"{format_lead(lead)}\nСоздана: {created}",
            reply_markup=lead_done_button(lead.id),
            parse_mode=None,  # имя клиента — пользовательский текст, не HTML
        )


@router.callback_query(F.data.startswith("lead_done:"))
async def lead_done(callback: CallbackQuery, lead_repository: LeadRepository) -> None:
    lead_id = int((callback.data or "").split(":")[1])
    await lead_repository.mark_done(lead_id)
    await callback.answer("Отмечено как обработанная")
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            f"{callback.message.text}\n\n✅ Обработано", parse_mode=None
        )


@router.message(Command("unanswered"))
async def unanswered(message: Message, unanswered_repository: UnansweredRepository) -> None:
    questions = await unanswered_repository.list_recent()
    if not questions:
        await message.answer("Вопросов без ответа нет 👍")
        return
    lines = [f"• {q.created_at:%d.%m %H:%M} — {q.question}" for q in questions]
    await message.answer(
        "❓ Последние вопросы без ответа (стоит дополнить документы):\n\n" + "\n".join(lines),
        parse_mode=None,
    )


@router.message(Command("reload"))
async def reload(message: Message, indexer: IndexerService, catalog: Catalog) -> None:
    await message.answer("Переиндексирую документы…")
    report = await indexer.sync(force=True)
    catalog.__dict__.update(load_catalog(indexer.docs_dir).__dict__)  # обновляем кнопочное меню
    await message.answer(
        f"Готово: файлов {report.indexed}, чанков {report.chunks}, удалено {report.removed}."
    )
