"""Хендлеры для клиентов: приветствие, вопросы, заявка менеджеру."""

import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.enums import ChatAction
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.bot import keyboards as kb
from app.services.leads import InvalidPhoneError, LeadService, format_lead
from app.services.qa import QAService

logger = logging.getLogger(__name__)
router = Router(name="client")


class LeadForm(StatesGroup):
    """Пошаговый диалог (FSM — конечный автомат): сначала имя, потом телефон."""

    name = State()
    phone = State()


@router.message(CommandStart())
async def start(message: Message, state: FSMContext, company_name: str) -> None:
    await state.clear()
    name = escape(message.from_user.first_name) if message.from_user else ""
    await message.answer(
        f"👋 Здравствуйте{', ' + name if name else ''}!\n\n"
        f"Я — онлайн-консультант <b>{escape(company_name)}</b> 🚗\n\n"
        "Что я умею:\n"
        "💰 показать цены на услуги\n"
        "📍 подсказать адрес и график работы\n"
        "🛡 рассказать про гарантию\n"
        "💬 ответить на любой вопрос по нашим документам\n"
        "📞 записать вас — менеджер перезвонит\n\n"
        "Выберите раздел в меню 👇 или просто напишите вопрос.",
        reply_markup=kb.main_menu(),
    )


# ---------- Заявка менеджеру ----------


@router.message(F.text == kb.CANCEL)
async def cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Хорошо, отменил. Задавайте вопросы!", reply_markup=kb.main_menu())


@router.message(StateFilter(None), F.text == kb.CONTACT_MANAGER)
async def contact_from_menu(message: Message, state: FSMContext) -> None:
    await _ask_name(message, state)


@router.callback_query(F.data == kb.CONTACT_CALLBACK)
async def contact_from_answer(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await _ask_name(callback.message, state)


async def _ask_name(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_state(LeadForm.name)
    await state.update_data(question=data.get("last_question"))
    await message.answer("Как к вам обращаться?", reply_markup=kb.cancel_menu())


@router.message(LeadForm.name, F.text)
async def got_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not 1 <= len(name) <= 100:
        await message.answer("Напишите, пожалуйста, имя (до 100 символов).")
        return
    await state.update_data(name=name)
    await state.set_state(LeadForm.phone)
    await message.answer(
        "Оставьте номер телефона — нажмите кнопку или напишите, например, 8 900 123-45-67.",
        reply_markup=kb.phone_menu(),
    )


@router.message(LeadForm.phone, F.contact | F.text)
async def got_phone(
    message: Message,
    state: FSMContext,
    bot: Bot,
    lead_service: LeadService,
    manager_chat_id: int,
) -> None:
    raw_phone = message.contact.phone_number if message.contact else (message.text or "")
    data = await state.get_data()
    try:
        lead = await lead_service.create(
            telegram_user_id=message.chat.id,
            name=data["name"],
            phone=raw_phone,
            question=data.get("question"),
        )
    except InvalidPhoneError:
        await message.answer("Не похоже на номер телефона. Попробуйте ещё раз, например 89001234567.")
        return

    await state.clear()
    await message.answer(
        f"✅ Спасибо, {escape(data['name'])}! Заявка #{lead.id} принята.\n"
        "Менеджер перезвонит вам в ближайшее рабочее время 📞",
        reply_markup=kb.main_menu(),
    )
    user = message.from_user
    username = f"\nTelegram: @{user.username}" if user and user.username else ""
    try:
        await bot.send_message(
            manager_chat_id,
            escape(f"🔔 Новая заявка!\n{format_lead(lead)}{username}"),
            reply_markup=kb.lead_done_button(lead.id),
        )
    except Exception:  # заявка уже в БД — не роняем диалог из-за уведомления
        logger.exception("Не удалось уведомить менеджера о заявке #%s", lead.id)


# ---------- Вопросы ----------


@router.message(StateFilter(None), F.text)
async def question(message: Message, state: FSMContext, bot: Bot, qa_service: QAService) -> None:
    text = (message.text or "").strip()
    if text.startswith("/"):
        await message.answer("Не знаю такой команды. Просто напишите вопрос.")
        return

    await state.update_data(last_question=text)
    # Локальная модель думает до минуты — показываем, что работа идёт
    waiting = await message.answer("🔎 Ищу ответ в документах сервиса…")
    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    try:
        answer = await qa_service.answer(message.chat.id, text)
    except Exception:
        logger.exception("Ошибка при ответе на вопрос")
        await waiting.edit_text(
            "😔 Извините, сейчас не получается ответить. Оставьте заявку — менеджер поможет.",
            reply_markup=kb.contact_manager_inline(),
        )
        return

    if answer.found:
        sources = ", ".join(answer.sources)
        # escape — чтобы символы < > & в ответе модели не сломали HTML-разметку Telegram
        await waiting.edit_text(
            f"💡 {escape(answer.text or '')}\n\n<i>📄 Источник: {escape(sources)}</i>",
            reply_markup=kb.contact_manager_inline(),
        )
    else:
        await waiting.edit_text(
            "🤔 В наших документах нет ответа на этот вопрос — не хочу вас обманывать.\n\n"
            "Оставьте заявку, и менеджер перезвонит и всё подскажет 👇",
            reply_markup=kb.contact_manager_inline(),
        )
