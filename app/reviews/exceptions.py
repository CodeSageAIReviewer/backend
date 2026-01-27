class ReviewDiffError(Exception):
    """Базовая ошибка получения diff для ревью."""


class DiffNotAvailableError(ReviewDiffError):
    """Diff недоступен (например, PR удалён/нет прав)."""


class LLMCallError(Exception):
    """Ошибка при вызове LLM."""
