"""Каталог для кнопочного меню: разделы прайса, частые вопросы и гарантия — прямо из data/docs.

Зачем, если есть LLM: на типовые вопросы («цены на шиномонтаж», «где вы») ответ нужен мгновенно
и дословно по документу. Кнопки берут текст из тех же файлов, поэтому меню обновляется
вместе с документами (после /reload) и никогда не расходится с ними.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

PRICE_FILE = "price.md"
FAQ_FILE = "faq.md"
CONDITIONS_FILE = "conditions.txt"


@dataclass(frozen=True)
class Section:
    title: str
    body: str


@dataclass
class Catalog:
    price_title: str = ""
    price_note: str = ""  # вступительный абзац прайса (например, «цены без запчастей»)
    prices: list[Section] = field(default_factory=list)
    faq: list[Section] = field(default_factory=list)
    conditions: list[Section] = field(default_factory=list)

    def faq_answer(self, *keywords: str) -> str | None:
        """Первый ответ из FAQ, в вопросе которого есть одно из слов."""
        for section in self.faq:
            if any(word in section.title.lower() for word in keywords):
                return section.body
        return None


def split_markdown(text: str) -> tuple[str, str, list[Section]]:
    """Markdown → (заголовок #, текст до первого ##, разделы ##)."""
    title_match = re.search(r"^#\s+(.+)$", text, flags=re.M)
    title = title_match.group(1).strip() if title_match else ""
    parts = re.split(r"^##\s+(.+)$", text, flags=re.M)
    intro = re.sub(r"^#\s+.+$", "", parts[0], flags=re.M).strip()
    sections = [
        Section(title=parts[i].strip(), body=parts[i + 1].strip())
        for i in range(1, len(parts) - 1, 2)
    ]
    return title, intro, sections


def split_conditions(text: str) -> list[Section]:
    """Абзацы вида «Заголовок. Текст…» → разделы."""
    sections = []
    for paragraph in re.split(r"\n\s*\n", text):
        title, dot, body = paragraph.strip().partition(". ")
        if dot and body and len(title) <= 40:
            sections.append(Section(title=title, body=body))
    return sections


def load_catalog(docs_dir: Path) -> Catalog:
    catalog = Catalog()
    if (path := docs_dir / PRICE_FILE).exists():
        catalog.price_title, catalog.price_note, catalog.prices = split_markdown(
            path.read_text(encoding="utf-8")
        )
    if (path := docs_dir / FAQ_FILE).exists():
        _, _, catalog.faq = split_markdown(path.read_text(encoding="utf-8"))
    if (path := docs_dir / CONDITIONS_FILE).exists():
        catalog.conditions = split_conditions(path.read_text(encoding="utf-8"))
    return catalog


def price_lines(section: Section) -> list[tuple[str, str]]:
    """«Замена масла — 900 рублей. Время — 30 минут.» → («Замена масла», «900 рублей. Время — 30 минут.»)."""
    items = []
    for line in section.body.splitlines():
        line = line.strip()
        if not line:
            continue
        name, dash, price = line.partition(" — ")
        items.append((name, price) if dash else (line, ""))
    return items
