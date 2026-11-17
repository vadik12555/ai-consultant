from app.rag.types import FoundChunk

NO_ANSWER_MARKER = "НЕТ_ОТВЕТА"


def build_system_prompt(company_name: str) -> str:
    return (
        f"Ты — вежливый консультант компании «{company_name}». "
        "Отвечай клиенту на русском языке, кратко и по делу (1–3 предложения), но обязательно "
        "упоминай важные условия и оговорки из фрагментов (цены, сроки, гарантию). "
        "Отвечай ТОЛЬКО на основе фрагментов "
        "документов компании, которые даны ниже. Ничего не придумывай: не называй цены, сроки "
        "и условия, которых нет во фрагментах. "
        f"Если во фрагментах нет ответа на вопрос, ответь ровно одним словом: {NO_ANSWER_MARKER}"
    )


def build_user_prompt(question: str, chunks: list[FoundChunk]) -> str:
    context = "\n\n".join(
        f"[Фрагмент {i}, файл {chunk.source}]\n{chunk.text}" for i, chunk in enumerate(chunks, 1)
    )
    return f"Фрагменты документов:\n\n{context}\n\nВопрос клиента: {question}"
