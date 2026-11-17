import pytest

from app.db.models import Lead
from app.services.leads import InvalidPhoneError, LeadService, format_lead, normalize_phone


class InMemoryLeadStore:
    def __init__(self) -> None:
        self.leads: list[Lead] = []

    async def add(self, telegram_user_id: int, name: str, phone: str, question: str | None) -> Lead:
        lead = Lead(
            id=len(self.leads) + 1,
            telegram_user_id=telegram_user_id,
            name=name,
            phone=phone,
            question=question,
        )
        self.leads.append(lead)
        return lead


@pytest.mark.parametrize(
    "raw",
    ["89001234567", "+7 900 123-45-67", "7(900)1234567", "9001234567", "8 (900) 123 45 67"],
)
def test_phone_formats_are_normalized(raw: str) -> None:
    assert normalize_phone(raw) == "+79001234567"


def test_tambov_landline_is_accepted() -> None:
    assert normalize_phone("8 (4752) 12-34-56") == "+74752123456"


@pytest.mark.parametrize("raw", ["", "12345", "abc", "+1 555 123 4567", "890012345678"])
def test_invalid_phones_are_rejected(raw: str) -> None:
    with pytest.raises(InvalidPhoneError):
        normalize_phone(raw)


async def test_create_lead_saves_normalized_data() -> None:
    store = InMemoryLeadStore()
    lead = await LeadService(store).create(42, "  Иван  ", "8 900 123-45-67", "Сколько стоит ТО?")

    assert store.leads == [lead]
    assert lead.name == "Иван"
    assert lead.phone == "+79001234567"
    assert lead.question == "Сколько стоит ТО?"
    assert "Заявка #1" in format_lead(lead)


async def test_create_lead_with_bad_phone_saves_nothing() -> None:
    store = InMemoryLeadStore()
    with pytest.raises(InvalidPhoneError):
        await LeadService(store).create(42, "Иван", "123")
    assert store.leads == []


async def test_create_lead_with_empty_name_fails() -> None:
    with pytest.raises(ValueError):
        await LeadService(InMemoryLeadStore()).create(42, "   ", "89001234567")
