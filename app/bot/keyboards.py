from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.services.catalog import Catalog

# Кнопки нижнего меню
PRICES = "💰 Цены"
CONTACTS = "📍 Адрес и график"
WARRANTY = "🛡 Гарантия"
FAQ = "❓ Частые вопросы"
ASK = "💬 Задать вопрос"
BOOK = "🗓 Онлайн-запись"
CONTACT_MANAGER = "📞 Менеджер"
CANCEL = "Отмена"

CONTACT_CALLBACK = "contact_manager"

_SECTION_EMOJI = {
    "обслуж": "🛢",
    "шин": "🛞",
    "ходов": "🛠",
    "тормоз": "🛑",
    "диагност": "🔍",
    "кондиц": "❄️",
}


def section_emoji(title: str) -> str:
    lowered = title.lower()
    return next((emoji for key, emoji in _SECTION_EMOJI.items() if key in lowered), "🔧")


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=PRICES), KeyboardButton(text=CONTACTS)],
            [KeyboardButton(text=WARRANTY), KeyboardButton(text=FAQ)],
            [KeyboardButton(text=ASK)],
            [KeyboardButton(text=BOOK), KeyboardButton(text=CONTACT_MANAGER)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Напишите вопрос или выберите раздел",
    )


def _contact_row() -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton(text="🗓 Записаться", callback_data="bk_start"),
        InlineKeyboardButton(text="📞 Менеджер", callback_data=CONTACT_CALLBACK),
    ]


def contact_manager_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[_contact_row()])


def price_sections(catalog: Catalog) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{section_emoji(s.title)} {s.title}", callback_data=f"price:{i}"
            )
        ]
        for i, s in enumerate(catalog.prices)
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_prices() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            _contact_row(),
            [InlineKeyboardButton(text="◀️ Все разделы", callback_data="prices")],
        ]
    )


def faq_questions(catalog: Catalog) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=s.title, callback_data=f"faq:{i}")]
        for i, s in enumerate(catalog.faq)
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_faq() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            _contact_row(),
            [InlineKeyboardButton(text="◀️ Все вопросы", callback_data="faq")],
        ]
    )


def cancel_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=CANCEL)]], resize_keyboard=True)


def phone_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить мой номер", request_contact=True)],
            [KeyboardButton(text=CANCEL)],
        ],
        resize_keyboard=True,
    )


def lead_done_button(lead_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Обработано", callback_data=f"lead_done:{lead_id}")]
        ]
    )
