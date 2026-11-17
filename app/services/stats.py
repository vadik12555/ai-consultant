from dataclasses import dataclass, field


@dataclass
class WeekStats:
    questions: int = 0
    unanswered: int = 0
    leads: int = 0
    bookings: int = 0
    top_services: list[tuple[str, int]] = field(default_factory=list)
    top_unanswered: list[str] = field(default_factory=list)

    @property
    def answered_percent(self) -> int:
        if not self.questions:
            return 0
        return round(100 * (self.questions - self.unanswered) / self.questions)


def format_stats(stats: WeekStats) -> str:
    lines = [
        "📊 Статистика за 7 дней\n",
        f"💬 Вопросов: {stats.questions}",
        f"✅ С ответом: {stats.answered_percent}%",
        f"🤔 Без ответа: {stats.unanswered}",
        f"📞 Заявок менеджеру: {stats.leads}",
        f"🗓 Онлайн-записей: {stats.bookings}",
    ]
    if stats.top_services:
        lines.append("\n🔝 Популярные услуги:")
        lines += [
            f"  {i}. {name} — {count}" for i, (name, count) in enumerate(stats.top_services, 1)
        ]
    if stats.top_unanswered:
        lines.append("\n📝 Стоит добавить в документы:")
        lines += [f"  • {question}" for question in stats.top_unanswered]
    return "\n".join(lines)
