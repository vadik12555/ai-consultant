"""Нарезка текста на куски (чанки).

Зачем: в LLM нельзя отправить все документы целиком, а искать по огромному тексту неточно.
Поэтому режем текст на куски ~chunk_size символов, стараясь не рвать абзацы и предложения.
Соседние куски «нахлёстываются» на overlap символов, чтобы мысль на границе не потерялась.
"""

import re

_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def split_into_chunks(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    if overlap >= chunk_size:
        raise ValueError("overlap должен быть меньше chunk_size")

    pieces = _split_to_pieces(text, chunk_size)
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        candidate = f"{current}\n{piece}" if current else piece
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        chunks.append(current)
        tail = _tail(current, overlap)
        current = f"{tail}\n{piece}" if tail and len(tail) + len(piece) + 1 <= chunk_size else piece
    if current:
        chunks.append(current)
    return chunks


def _split_to_pieces(text: str, max_len: int) -> list[str]:
    """Абзацы → (если длинный) предложения → (если всё ещё длинное) жёсткая нарезка."""
    pieces: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= max_len:
            pieces.append(paragraph)
            continue
        for sentence in _SENTENCE_END.split(paragraph):
            for start in range(0, len(sentence), max_len):
                pieces.append(sentence[start : start + max_len])
    return pieces


def _tail(text: str, size: int) -> str:
    """Последние ~size символов, начиная с границы слова."""
    if size <= 0 or len(text) <= size:
        return text if size > 0 else ""
    tail = text[-size:]
    space = tail.find(" ")
    return tail[space + 1 :] if space != -1 else tail
