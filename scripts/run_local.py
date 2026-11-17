"""Запуск без Docker (для машин, где Docker недоступен).

Поднимает встроенный PostgreSQL с pgvector (пакет pgserver), применяет миграции и запускает бота.
Ollama должна быть установлена и запущена отдельно (https://ollama.com), модели — скачаны:
    ollama pull qwen2.5:3b && ollama pull bge-m3

Запуск:  python scripts/run_local.py
"""

import os
import subprocess
import sys
from pathlib import Path

import pgserver

ROOT = Path(__file__).resolve().parent.parent
# Путь только латиницей: Postgres на Windows плохо переносит кириллицу в путях
PG_DATA = Path(os.environ.get("LOCAL_PG_DATA", "C:/dtemp/pgdata"))


def main() -> None:
    server = pgserver.get_server(PG_DATA, cleanup_mode=None)  # база переживает перезапуски
    server.psql("CREATE EXTENSION IF NOT EXISTS vector;")
    url = server.get_uri().replace("postgresql://", "postgresql+asyncpg://", 1)

    env = {
        **os.environ,
        "DATABASE_URL": url,
        "OLLAMA_URL": os.environ.get("OLLAMA_URL", "http://localhost:11434"),
    }
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, check=True)
    subprocess.run([sys.executable, "-m", "app.main"], cwd=ROOT, env=env, check=True)


if __name__ == "__main__":
    main()
