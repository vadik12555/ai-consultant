import hashlib
import math


class FakeEmbedder:
    """Детерминированные «эмбеддинги» для тестов: мешок слов, захешированный в вектор.

    Тексты с общими словами получаются похожими — этого достаточно, чтобы проверять поиск без сети.
    """

    def __init__(self, dim: int = 64) -> None:
        self.dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for word in text.lower().split():
            word = word.strip('.,!?:;«»"()')
            if word:
                index = int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dim
                vector[index] += 1.0
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        return [x / norm for x in vector]


class FakeLLM:
    """Возвращает заранее заданный ответ и запоминает, что ему передали."""

    def __init__(self, answer: str = "Тестовый ответ") -> None:
        self.answer = answer
        self.calls: list[tuple[str, str]] = []

    async def generate(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.answer
