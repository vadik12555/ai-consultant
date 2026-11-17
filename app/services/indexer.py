import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

from app.db.repositories import DocumentRepository
from app.llm.base import Embedder
from app.rag.chunking import split_into_chunks
from app.rag.loaders import list_documents, load_text

logger = logging.getLogger(__name__)


@dataclass
class IndexReport:
    indexed: int = 0  # файлов проиндексировано заново
    skipped: int = 0  # файлов не менялось
    removed: int = 0  # документов удалено из БД (файл исчез)
    chunks: int = 0  # кусков сохранено


class IndexerService:
    """Синхронизирует data/docs с базой: новые и изменённые файлы → чанки → векторы → pgvector."""

    def __init__(
        self,
        repository: DocumentRepository,
        embedder: Embedder,
        docs_dir: Path,
        chunk_size: int,
        chunk_overlap: int,
    ) -> None:
        self._repository = repository
        self._embedder = embedder
        self.docs_dir = docs_dir
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    async def sync(self, force: bool = False) -> IndexReport:
        report = IndexReport()
        known_hashes = {} if force else await self._repository.get_hashes()
        files = list_documents(self.docs_dir)

        for path in files:
            sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            if known_hashes.get(path.name) == sha256:
                report.skipped += 1
                continue
            texts = split_into_chunks(load_text(path), self._chunk_size, self._chunk_overlap)
            if not texts:
                logger.warning("Файл %s пустой — пропускаю", path.name)
                continue
            embeddings = await self._embedder.embed(texts)
            await self._repository.replace(path.name, sha256, texts, embeddings)
            report.indexed += 1
            report.chunks += len(texts)
            logger.info("Проиндексирован %s: %d чанков", path.name, len(texts))

        report.removed = await self._repository.delete_missing({p.name for p in files})
        return report
