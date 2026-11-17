from app.services.stats import WeekStats, format_stats


def test_answered_percent() -> None:
    assert WeekStats(questions=10, unanswered=3).answered_percent == 70
    assert WeekStats().answered_percent == 0  # без деления на ноль


def test_format_stats_shows_key_numbers() -> None:
    text = format_stats(
        WeekStats(
            questions=20,
            unanswered=5,
            leads=3,
            bookings=4,
            top_services=[("Шиномонтаж", 3)],
            top_unanswered=["Есть ли эвакуатор?"],
        )
    )
    assert "Вопросов: 20" in text
    assert "75%" in text
    assert "Шиномонтаж — 3" in text
    assert "Есть ли эвакуатор?" in text
