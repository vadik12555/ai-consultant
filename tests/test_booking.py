from datetime import date, datetime, timedelta

import pytest

from app.db.models import Booking
from app.services.booking import (
    TIMEZONE,
    BookingService,
    SlotTakenError,
    day_slots,
    free_slots,
)

MONDAY = date(2026, 11, 16)
SUNDAY = date(2026, 11, 22)
EARLY_MONDAY = datetime(2026, 11, 16, 6, 0, tzinfo=TIMEZONE)


def at(day: date, hour: int) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=TIMEZONE)


class InMemoryBookingStore:
    """Повторяет поведение уникального индекса БД: один активный слот — одна запись."""

    def __init__(self) -> None:
        self.bookings: list[Booking] = []

    async def busy_slots(self, start: datetime, end: datetime) -> set[datetime]:
        return {b.starts_at for b in self.bookings if start <= b.starts_at < end}

    async def add(
        self, telegram_user_id: int, name: str, phone: str, service: str, starts_at: datetime
    ) -> Booking:
        if any(b.starts_at == starts_at for b in self.bookings):
            raise SlotTakenError(starts_at)
        booking = Booking(
            id=len(self.bookings) + 1,
            telegram_user_id=telegram_user_id,
            name=name,
            phone=phone,
            service=service,
            starts_at=starts_at,
        )
        self.bookings.append(booking)
        return booking


def test_weekday_schedule_8_to_20() -> None:
    slots = day_slots(MONDAY)
    assert slots[0] == at(MONDAY, 8)
    assert slots[-1] == at(MONDAY, 19)  # последний час заканчивается ровно в 20:00
    assert len(slots) == 12


def test_sunday_schedule_9_to_17() -> None:
    slots = day_slots(SUNDAY)
    assert (slots[0], slots[-1], len(slots)) == (at(SUNDAY, 9), at(SUNDAY, 16), 8)


def test_busy_and_past_slots_are_hidden() -> None:
    now = at(MONDAY, 10) + timedelta(minutes=30)  # 10:30 → ближайший слот 12:00 (минимум час)
    slots = free_slots(MONDAY, busy={at(MONDAY, 13)}, now=now)
    assert slots[0] == at(MONDAY, 12)
    assert at(MONDAY, 13) not in slots


def test_booking_days_are_next_week() -> None:
    days = BookingService(InMemoryBookingStore()).booking_days(EARLY_MONDAY)
    assert days[0] == MONDAY and len(days) == 7


async def test_book_saves_normalized_booking() -> None:
    store = InMemoryBookingStore()
    booking = await BookingService(store).book(
        1, " Иван ", "8 900 123-45-67", "Шиномонтаж", at(MONDAY, 10), now=EARLY_MONDAY
    )
    assert (booking.name, booking.phone) == ("Иван", "+79001234567")
    assert store.bookings == [booking]


async def test_same_slot_cannot_be_booked_twice() -> None:
    service = BookingService(InMemoryBookingStore())
    await service.book(1, "Иван", "89001234567", "ТО", at(MONDAY, 10), now=EARLY_MONDAY)
    with pytest.raises(SlotTakenError):
        await service.book(2, "Пётр", "89007654321", "ТО", at(MONDAY, 10), now=EARLY_MONDAY)


async def test_slot_outside_schedule_is_rejected() -> None:
    service = BookingService(InMemoryBookingStore())
    with pytest.raises(SlotTakenError):
        await service.book(1, "Иван", "89001234567", "ТО", at(MONDAY, 22), now=EARLY_MONDAY)


async def test_free_slots_reflect_existing_bookings() -> None:
    service = BookingService(InMemoryBookingStore())
    await service.book(1, "Иван", "89001234567", "ТО", at(MONDAY, 10), now=EARLY_MONDAY)
    slots = await service.free_slots(MONDAY, now=EARLY_MONDAY)
    assert at(MONDAY, 10) not in slots and at(MONDAY, 11) in slots
