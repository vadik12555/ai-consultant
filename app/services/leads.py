import re
from typing import Protocol

from app.db.models import Lead


class InvalidPhoneError(ValueError):
    pass


class LeadStore(Protocol):
    async def add(
        self, telegram_user_id: int, name: str, phone: str, question: str | None
    ) -> Lead: ...


def normalize_phone(raw: str) -> str:
    """Приводит российский номер к виду +7XXXXXXXXXX. Принимает 8..., +7..., 7... и 10 цифр."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits[0] in "78":
        digits = digits[1:]
    if len(digits) != 10 or digits[0] not in "3489":  # коды РФ начинаются с 3, 4, 8 или 9
        raise InvalidPhoneError(raw)
    return f"+7{digits}"


class LeadService:
    def __init__(self, store: LeadStore) -> None:
        self._store = store

    async def create(
        self, telegram_user_id: int, name: str, phone: str, question: str | None = None
    ) -> Lead:
        name = name.strip()
        if not 1 <= len(name) <= 100:
            raise ValueError("Имя должно быть от 1 до 100 символов")
        return await self._store.add(telegram_user_id, name, normalize_phone(phone), question)


def format_lead(lead: Lead) -> str:
    lines = [f"📝 Заявка #{lead.id}", f"Имя: {lead.name}", f"Телефон: {lead.phone}"]
    if lead.question:
        lines.append(f"Вопрос: {lead.question}")
    return "\n".join(lines)
