"""Кнопочное меню: цены по разделам, адрес и график, гарантия, частые вопросы. Работает без LLM."""

from html import escape

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from app.bot import keyboards as kb
from app.services.catalog import Catalog, price_lines

router = Router(name="menu")
router.message.filter(StateFilter(None))  # во время оформления заявки меню не перехватывает ввод


async def _edit_or_send(callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup) -> None:
    """Меняем текущее сообщение, а не шлём новое — меню не засоряет чат."""
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=markup)


# ---------- Цены ----------


def _prices_overview(catalog: Catalog) -> str:
    note = f"\n<i>{escape(catalog.price_note)}</i>" if catalog.price_note else ""
    return f"💰 <b>Цены</b>{note}\n\nВыберите раздел:"


@router.message(F.text == kb.PRICES)
async def prices(message: Message, catalog: Catalog) -> None:
    await message.answer(_prices_overview(catalog), reply_markup=kb.price_sections(catalog))


@router.callback_query(F.data == "prices")
async def prices_back(callback: CallbackQuery, catalog: Catalog) -> None:
    await _edit_or_send(callback, _prices_overview(catalog), kb.price_sections(catalog))


@router.callback_query(F.data.startswith("price:"))
async def price_section(callback: CallbackQuery, catalog: Catalog) -> None:
    index = int((callback.data or "").split(":")[1])
    if index >= len(catalog.prices):
        await callback.answer("Раздел устарел, откройте меню цен заново")
        return
    section = catalog.prices[index]
    lines = [f"{kb.section_emoji(section.title)} <b>{escape(section.title)}</b>\n"]
    for name, price in price_lines(section):
        lines.append(f"▫️ {escape(name)}" + (f" — <b>{escape(price)}</b>" if price else ""))
    await _edit_or_send(callback, "\n".join(lines), kb.back_to_prices())


# ---------- Частые вопросы ----------


@router.message(F.text == kb.FAQ)
async def faq(message: Message, catalog: Catalog) -> None:
    await message.answer("❓ <b>Частые вопросы</b>", reply_markup=kb.faq_questions(catalog))


@router.callback_query(F.data == "faq")
async def faq_back(callback: CallbackQuery, catalog: Catalog) -> None:
    await _edit_or_send(callback, "❓ <b>Частые вопросы</b>", kb.faq_questions(catalog))


@router.callback_query(F.data.startswith("faq:"))
async def faq_answer(callback: CallbackQuery, catalog: Catalog) -> None:
    index = int((callback.data or "").split(":")[1])
    if index >= len(catalog.faq):
        await callback.answer("Вопрос устарел, откройте список заново")
        return
    section = catalog.faq[index]
    text = f"❓ <b>{escape(section.title)}</b>\n\n{escape(section.body)}"
    await _edit_or_send(callback, text, kb.back_to_faq())


# ---------- Адрес, гарантия ----------


@router.message(F.text == kb.CONTACTS)
async def contacts(message: Message, catalog: Catalog) -> None:
    parts = ["📍 <b>Как нас найти</b>"]
    if address := catalog.faq_answer("где", "находит"):
        parts.append(f"\n🏠 {escape(address)}")
    if schedule := catalog.faq_answer("график", "работ"):
        parts.append(f"\n🕗 {escape(schedule)}")
    if booking := catalog.faq_answer("записат"):
        parts.append(f"\n📝 {escape(booking)}")
    await message.answer("\n".join(parts), reply_markup=kb.contact_manager_inline())


@router.message(F.text == kb.WARRANTY)
async def warranty(message: Message, catalog: Catalog) -> None:
    relevant = [s for s in catalog.conditions if "гарант" in s.title.lower()]
    parts = ["🛡 <b>Гарантия</b>"]
    parts += [f"\n<b>{escape(s.title)}.</b> {escape(s.body)}" for s in relevant]
    await message.answer("\n".join(parts), reply_markup=kb.contact_manager_inline())


@router.message(F.text == kb.ASK)
async def ask(message: Message) -> None:
    await message.answer(
        "💬 Напишите вопрос своими словами — например:\n"
        "<i>«Сколько стоит заменить колодки и тормозную жидкость?»</i>\n\n"
        "Я найду ответ в документах сервиса. Это займёт до минуты ⏳"
    )
