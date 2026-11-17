from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Все настройки берутся из переменных окружения / файла .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: str
    manager_chat_id: int
    company_name: str = "Автосервис «Мотор» (Тамбов)"

    database_url: str = "postgresql+asyncpg://app:app@db:5432/app"

    ollama_url: str = "http://ollama:11434"
    llm_model: str = "qwen2.5:3b"
    embed_model: str = "bge-m3"
    embed_dim: int = 1024  # размерность векторов bge-m3

    docs_dir: Path = Path("data/docs")
    chunk_size: int = 500  # символов в одном куске
    chunk_overlap: int = 100  # сколько символов «нахлёста» между соседними кусками
    top_k: int = 5
    min_score: float = 0.5  # ниже этой похожести считаем, что ответа в документах нет


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
