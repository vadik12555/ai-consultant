import pytest

from app.rag.chunking import split_into_chunks


def test_short_text_is_one_chunk() -> None:
    assert split_into_chunks("Замена масла — 900 рублей.", chunk_size=100, overlap=10) == [
        "Замена масла — 900 рублей."
    ]


def test_empty_text_gives_no_chunks() -> None:
    assert split_into_chunks("  \n\n  ", chunk_size=100, overlap=10) == []


def test_chunks_respect_size_limit() -> None:
    text = "\n\n".join(f"Абзац номер {i}. " + "слово " * 30 for i in range(20))
    chunks = split_into_chunks(text, chunk_size=300, overlap=50)
    assert len(chunks) > 1
    assert all(len(chunk) <= 300 for chunk in chunks)


def test_paragraphs_are_not_cut_when_they_fit() -> None:
    paragraphs = ["Первый абзац про масло.", "Второй абзац про шины.", "Третий про тормоза."]
    chunks = split_into_chunks("\n\n".join(paragraphs), chunk_size=50, overlap=0)
    for paragraph in paragraphs:
        assert any(paragraph in chunk for chunk in chunks)


def test_neighbour_chunks_overlap() -> None:
    text = "\n\n".join(f"Предложение номер {i} про автосервис." for i in range(30))
    chunks = split_into_chunks(text, chunk_size=200, overlap=60)
    for previous, current in zip(chunks, chunks[1:]):
        first_line_of_current = current.split("\n")[0]
        assert first_line_of_current in previous  # начало следующего куска повторяет конец предыдущего


def test_very_long_sentence_is_hard_split() -> None:
    chunks = split_into_chunks("а" * 1000, chunk_size=300, overlap=0)
    assert all(len(chunk) <= 300 for chunk in chunks)
    assert "".join(chunks) == "а" * 1000


def test_overlap_must_be_smaller_than_size() -> None:
    with pytest.raises(ValueError):
        split_into_chunks("текст", chunk_size=100, overlap=100)
