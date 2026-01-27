from __future__ import annotations

from django.conf import settings
from django.db import models

# --- Enums ---


class ReviewStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    RUNNING = "running", "Running"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"
    CANCELED = "canceled", "Canceled"


class CommentSeverity(models.TextChoices):
    INFO = "info", "Info"
    WARNING = "warning", "Warning"
    ERROR = "error", "Error"


class CommentType(models.TextChoices):
    GENERAL = "general", "General"
    CODE_SMELL = "code_smell", "Code Smell"
    BUG = "bug", "Bug"
    SECURITY = "security", "Security"
    PERFORMANCE = "performance", "Performance"
    STYLE = "style", "Style"
    TESTS = "tests", "Tests"
    DOCUMENTATION = "documentation", "Documentation"


# --- Models ---


class ReviewRun(models.Model):
    """
    Один запуск AI-ревью по конкретному MergeRequest.
    Это "job": имеет статус, входные данные, метаданные и результат.
    """

    merge_request = models.ForeignKey(
        "code_hosts.MergeRequest",
        on_delete=models.CASCADE,
        related_name="review_runs",
    )

    # Кто запустил
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="requested_review_runs",
    )

    # Какая LLM-интеграция использовалась (глобальная интеграция)
    llm_integration = models.ForeignKey(
        "llm.LLMIntegration",
        on_delete=models.PROTECT,
        related_name="review_runs",
    )

    status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.QUEUED,
        db_index=True,
    )

    # Входные данные (что именно отправляли в LLM). Храним для воспроизводимости.
    # Можно складывать diff, описание MR, список файлов, контекст RAG и т.п.
    input_payload = models.JSONField(default=dict, blank=True)

    # Сырые/структурированные выходы
    raw_output = models.TextField(blank=True)  # полный текст ответа LLM
    structured_output = models.JSONField(
        default=dict, blank=True
    )  # распарсенный JSON/структура

    # Метаданные модели/параметры вызова (на случай переопределений поверх default_model)
    model_name = models.CharField(max_length=255, blank=True)
    temperature = models.FloatField(null=True, blank=True)
    max_tokens = models.IntegerField(null=True, blank=True)

    # Ошибка/диагностика
    error_message = models.TextField(blank=True)

    # Тайминги
    queued_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-queued_at"]
        indexes = [
            models.Index(fields=["merge_request", "status"]),
            models.Index(fields=["llm_integration", "status"]),
        ]
        verbose_name = "Review run"
        verbose_name_plural = "Review runs"

    def __str__(self) -> str:
        return f"ReviewRun(mr={self.merge_request_id}, status={self.status})"


class ReviewComment(models.Model):
    """
    Нормализованные замечания/комментарии, которые получились из ReviewRun.
    Их удобно:
    - показывать в UI,
    - фильтровать по severity/type,
    - потом публиковать в GitLab/GitHub.
    """

    review_run = models.ForeignKey(
        ReviewRun,
        on_delete=models.CASCADE,
        related_name="comments",
    )

    severity = models.CharField(
        max_length=20,
        choices=CommentSeverity.choices,
        default=CommentSeverity.INFO,
        db_index=True,
    )

    comment_type = models.CharField(
        max_length=30,
        choices=CommentType.choices,
        default=CommentType.GENERAL,
        db_index=True,
    )

    title = models.CharField(max_length=255, blank=True)
    body = models.TextField()

    # Привязка к месту в коде (опционально)
    file_path = models.CharField(max_length=1024, blank=True)
    line_start = models.IntegerField(null=True, blank=True)
    line_end = models.IntegerField(null=True, blank=True)

    # Если LLM предложила патч/правку
    suggestion = models.TextField(blank=True)

    # Публиковали ли обратно в Git (опционально для будущего)
    posted_to_vcs = models.BooleanField(default=False)
    posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["review_run", "severity"]),
            models.Index(fields=["review_run", "comment_type"]),
        ]
        verbose_name = "Review comment"
        verbose_name_plural = "Review comments"

    def __str__(self) -> str:
        return f"ReviewComment(run={self.review_run_id}, severity={self.severity})"
