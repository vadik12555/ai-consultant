"""Онлайн-запись: расписание, свободные слоты, бронирование без двойных записей."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from app.db.models import Booking
from app.services.leads import normalize_phone

TIMEZONE = ZoneInfo("Europe/Moscow")  # Тамбов живёт по московскому времени

# График из faq.md: Пн–Сб 8:00–20:00, Вс 9:00–17:00. Ключ — номер дня недели (0 = понедельник).
WORKING_HOURS: dict[int, tuple[time, time]] = {
    **{weekday: (time(8), time(20)) for weekday in range(6)},
    6: (time(9), time(17)),
}
SLOT_MINUTES = 60
MIN_LEAD_TIME = timedelta(hours=1)  # нельзя записаться «на через 5 минут»
BOOKING_DAYS_AHEAD = 7


class SlotTakenError(Exception):
    """Слот уже занят (или стал занят, пока клиент выбирал)."""


class BookingStore(Protocol):
    async def busy_slots(self, start: datetime, end: datetime) -> set[datetime]: ...

    async def add(
        self, telegram_user_id: int, name: str, phone: str, service: str, starts_at: datetime
    ) -> Booking:
        """Должен бросить SlotTakenError, если слот уже занят."""
        ...


@dataclass(frozen=True)
class DaySchedule:
    day: date
    slots: list[datetime]


def day_slots(day: date) -> list[datetime]:
    """Все слоты рабочего дня по графику, без учёта занятости."""
    opens, closes = WORKING_HOURS[day.weekday()]
    current = datetime.combine(day, opens, tzinfo=TIMEZONE)
    end = datetime.combine(day, closes, tzinfo=TIMEZONE)
    slots = []
    while current + timedelta(minutes=SLOT_MINUTES) <= end:
        slots.append(current)
        current += timedelta(minutes=SLOT_MINUTES)
    return slots


def free_slots(day: date, busy: set[datetime], now: datetime) -> list[datetime]:
    earliest = now + MIN_LEAD_TIME
    return [slot for slot in day_slots(day) if slot not in busy and slot >= earliest]


class BookingService:
    def __init__(self, store: BookingStore) -> None:
        self._store = store

    @staticmethod
    def now() -> datetime:
        return datetime.now(TIMEZONE)

    def booking_days(self, now: datetime | None = None) -> list[date]:
        today = (now or self.now()).date()
        return [today + timedelta(days=i) for i in range(BOOKING_DAYS_AHEAD)]

    async def free_slots(self, day: date, now: datetime | None = None) -> list[datetime]:
        start = datetime.combine(day, time(0), tzinfo=TIMEZONE)
        busy = await self._store.busy_slots(start, start + timedelta(days=1))
        return free_slots(day, busy, now or self.now())

    async def book(
        self,
        telegram_user_id: int,
        name: str,
        phone: str,
        service: str,
        starts_at: datetime,
        now: datetime | None = None,
    ) -> Booking:
        name = name.strip()
        if not 1 <= len(name) <= 100:
            raise ValueError("Имя должно быть от 1 до 100 символов")
        phone = normalize_phone(phone)
        # Повторная проверка: пока клиент вводил имя и телефон, слот могли занять или он «протух»
        if starts_at not in await self.free_slots(starts_at.date(), now):
            raise SlotTakenError(starts_at)
        return await self._store.add(telegram_user_id, name, phone, service, starts_at)


WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def format_day(day: date) -> str:
    return f"{WEEKDAYS[day.weekday()]} {day:%d.%m}"


def format_booking(booking: Booking) -> str:
    starts = booking.starts_at.astimezone(TIMEZONE)
    return (
        f"🗓 Запись #{booking.id}\n"
        f"Когда: {format_day(starts.date())} в {starts:%H:%M}\n"
        f"Услуга: {booking.service}\n"
        f"Имя: {booking.name}\n"
        f"Телефон: {booking.phone}"
    )
