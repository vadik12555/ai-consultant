from pathlib import Path

from app.services.catalog import load_catalog, price_lines, split_conditions, split_markdown

DOCS = Path(__file__).resolve().parent.parent / "data" / "docs"


def test_split_markdown_sections() -> None:
    title, intro, sections = split_markdown("# Прайс\n\nВступление.\n\n## Шины\n\nА — 1\n\n## ТО\n\nБ — 2")
    assert title == "Прайс"
    assert intro == "Вступление."
    assert [s.title for s in sections] == ["Шины", "ТО"]
    assert sections[1].body == "Б — 2"


def test_price_lines_split_name_and_price() -> None:
    [section] = split_markdown("## ТО\n\nЗамена масла — 900 рублей.\n\nБез цены")[2]
    assert price_lines(section) == [("Замена масла", "900 рублей."), ("Без цены", "")]


def test_split_conditions_by_paragraph_title() -> None:
    sections = split_conditions("Шапка без точки\n\nГарантия на работы. 6 месяцев.\n\nОплата. После работ.")
    assert [s.title for s in sections] == ["Гарантия на работы", "Оплата"]


def test_demo_catalog_is_complete() -> None:
    catalog = load_catalog(DOCS)
    assert len(catalog.prices) >= 5
    assert catalog.faq_answer("график") and "8:00" in catalog.faq_answer("график")
    assert any("гарант" in s.title.lower() for s in catalog.conditions)
