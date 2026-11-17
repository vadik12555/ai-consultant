"""Онлайн-запись: услуга → день → время → имя → телефон → подтверждение."""

import logging
from datetime import date, datetime
from html import escape

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot import keyboards as kb
from app.services.booking import (
    TIMEZONE,
    BookingService,
    SlotTakenError,
    format_booking,
    format_day,
)
from app.services.catalog import Catalog
from app.services.leads import InvalidPhoneError, normalize_phone

logger = logging.getLogger(__name__)
router = Router(name="booking")

OTHER_SERVICE = "Другое / не знаю"


class BookingForm(StatesGroup):
    choosing = State()  # услуга, день и время выбираются кнопками
    name = State()
    phone = State()
    confirm = State()


def _button(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def _services_keyboard(catalog: Catalog) -> InlineKeyboardMarkup:
    titles = [s.title for s in catalog.prices] + [OTHER_SERVICE]
    rows = [[_button(f"{kb.section_emoji(t)} {t}", f"bk_srv:{i}")] for i, t in enumerate(titles)]
    rows.append([_button("✖️ Отмена", "bk_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _days_keyboard(days: list[date]) -> InlineKeyboardMarkup:
    buttons = [_button(format_day(day), f"bk_day:{day.isoformat()}") for day in days]
    rows = [buttons[i : i + 3] for i in range(0, len(buttons), 3)]
    rows.append([_button("◀️ Назад", "bk_start"), _button("✖️ Отмена", "bk_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _slots_keyboard(slots: list[datetime]) -> InlineKeyboardMarkup:
    buttons = [_button(f"{slot:%H:%M}", f"bk_slot:{slot.isoformat()}") for slot in slots]
    rows = [buttons[i : i + 4] for i in range(0, len(buttons), 4)]
    rows.append([_button("◀️ Другой день", "bk_days"), _button("✖️ Отмена", "bk_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_button("✅ Подтвердить", "bk_ok"), _button("✖️ Отмена", "bk_cancel")]]
    )


async def _edit(callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=markup)


# ---------- Шаг 1: услуга ----------


@router.message(F.text == kb.BOOK)
async def start_from_menu(message: Message, state: FSMContext, catalog: Catalog) -> None:
    await state.clear()
    await state.set_state(BookingForm.choosing)
    await message.answer(
        "🗓 <b>Онлайн-запись</b>\n\nШаг 1 из 4. Выберите услугу:",
        reply_markup=_services_keyboard(catalog),
    )


@router.callback_query(F.data == "bk_start")
async def start_from_button(callback: CallbackQuery, state: FSMContext, catalog: Catalog) -> None:
    await state.set_state(BookingForm.choosing)
    await _edit(
        callback,
        "🗓 <b>Онлайн-запись</b>\n\nШаг 1 из 4. Выберите услугу:",
        _services_keyboard(catalog),
    )


@router.callback_query(F.data.startswith("bk_srv:"))
async def choose_service(
    callback: CallbackQuery, state: FSMContext, catalog: Catalog, booking_service: BookingService
) -> None:
    index = int((callback.data or "").split(":")[1])
    titles = [s.title for s in catalog.prices] + [OTHER_SERVICE]
    if index >= len(titles):
        await callback.answer("Список услуг обновился, начните заново")
        return
    await state.set_state(BookingForm.choosing)
    await state.update_data(service=titles[index])
    await _show_days(callback, state, booking_service)


@router.callback_query(F.data == "bk_days")
async def back_to_days(
    callback: CallbackQuery, state: FSMContext, booking_service: BookingService
) -> None:
    await _show_days(callback, state, booking_service)


async def _show_days(
    callback: CallbackQuery, state: FSMContext, booking_service: BookingService
) -> None:
    data = await state.get_data()
    await _edit(
        callback,
        f"🗓 Услуга: <b>{escape(data.get('service', ''))}</b>\n\nШаг 2 из 4. Выберите день:",
        _days_keyboard(booking_service.booking_days()),
    )


# ---------- Шаг 2–3: день и время ----------


@router.callback_query(F.data.startswith("bk_day:"))
async def choose_day(
    callback: CallbackQuery, state: FSMContext, booking_service: BookingService
) -> None:
    day = date.fromisoformat((callback.data or "").split(":", 1)[1])
    slots = await booking_service.free_slots(day)
    if not slots:
        await callback.answer(
            "На этот день свободного времени нет — выберите другой", show_alert=True
        )
        return
    data = await state.get_data()
    await _edit(
        callback,
        f"🗓 Услуга: <b>{escape(data.get('service', ''))}</b>\n"
        f"📅 День: <b>{format_day(day)}</b>\n\nШаг 3 из 4. Свободное время:",
        _slots_keyboard(slots),
    )


@router.callback_query(F.data.startswith("bk_slot:"))
async def choose_slot(callback: CallbackQuery, state: FSMContext) -> None:
    slot = datetime.fromisoformat((callback.data or "").split(":", 1)[1])
    await state.update_data(starts_at=slot.isoformat())
    await state.set_state(BookingForm.name)
    data = await state.get_data()
    await _edit(
        callback,
        f"🗓 Услуга: <b>{escape(data.get('service', ''))}</b>\n"
        f"📅 Когда: <b>{format_day(slot.date())} в {slot:%H:%M}</b>\n\n"
        "Шаг 4 из 4. Как к вам обращаться?",
        None,
    )


# ---------- Шаг 4: контакты и подтверждение ----------


@router.message(BookingForm.name, F.text)
async def got_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if name == kb.CANCEL:
        await _cancel(message, state)
        return
    if not 1 <= len(name) <= 100:
        await message.answer("Напишите, пожалуйста, имя (до 100 символов).")
        return
    await state.update_data(name=name)
    await state.set_state(BookingForm.phone)
    await message.answer("📱 Ваш номер телефона:", reply_markup=kb.phone_menu())


@router.message(BookingForm.phone, F.contact | F.text)
async def got_phone(message: Message, state: FSMContext) -> None:
    if message.text == kb.CANCEL:
        await _cancel(message, state)
        return
    raw = message.contact.phone_number if message.contact else (message.text or "")
    try:
        phone = normalize_phone(raw)
    except InvalidPhoneError:
        await message.answer(
            "Не похоже на номер телефона. Попробуйте ещё раз, например 89001234567."
        )
        return
    await state.update_data(phone=phone)
    await state.set_state(BookingForm.confirm)
    data = await state.get_data()
    slot = datetime.fromisoformat(data["starts_at"]).astimezone(TIMEZONE)
    await message.answer("Проверьте данные 👇", reply_markup=kb.main_menu())
    await message.answer(
        "🗓 <b>Ваша запись</b>\n\n"
        f"🔧 {escape(data['service'])}\n"
        f"📅 {format_day(slot.date())} в {slot:%H:%M}\n"
        f"👤 {escape(data['name'])}\n"
        f"📱 {phone}",
        reply_markup=_confirm_keyboard(),
    )


@router.callback_query(BookingForm.confirm, F.data == "bk_ok")
async def confirm(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    booking_service: BookingService,
    manager_chat_id: int,
) -> None:
    data = await state.get_data()
    try:
        booking = await booking_service.book(
            telegram_user_id=callback.from_user.id,
            name=data["name"],
            phone=data["phone"],
            service=data["service"],
            starts_at=datetime.fromisoformat(data["starts_at"]),
        )
    except SlotTakenError:
        await state.set_state(BookingForm.choosing)
        await _edit(
            callback,
            "😔 Это время только что заняли. Выберите другое:",
            InlineKeyboardMarkup(inline_keyboard=[[_button("📅 Выбрать день", "bk_days")]]),
        )
        return

    await state.clear()
    slot = booking.starts_at.astimezone(TIMEZONE)
    await _edit(
        callback,
        f"✅ <b>Вы записаны!</b> Запись #{booking.id}\n\n"
        f"🔧 {escape(booking.service)}\n"
        f"📅 {format_day(slot.date())} в {slot:%H:%M}\n\n"
        "📍 Ждём вас по адресу из раздела «Адрес и график». Если планы изменятся — "
        "напишите менеджеру.",
        None,
    )
    try:
        await bot.send_message(
            manager_chat_id, f"🔔 Новая онлайн-запись!\n{format_booking(booking)}", parse_mode=None
        )
    except Exception:
        logger.exception("Не удалось уведомить менеджера о записи #%s", booking.id)


@router.callback_query(F.data == "bk_cancel")
async def cancel_button(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _edit(callback, "Запись отменена. Возвращайтесь, когда будет удобно 🙂", None)


async def _cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Запись отменена.", reply_markup=kb.main_menu())
