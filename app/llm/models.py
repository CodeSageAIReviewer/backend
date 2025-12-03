from django.conf import settings
from django.db import models

from code_hosts.models.workspace import Workspace
from common.models import SimpleBaseModel


class LLMProvider(models.TextChoices):
    OPENAI = "openai", "OpenAI ChatGPT"
    DEEPSEEK = "deepseek", "DeepSeek"
    OLLAMA = "ollama", "Ollama (Local)"


class LLMIntegration(SimpleBaseModel):
    """
    Хранит подключение рабочей зоны к конкретному LLM-провайдеру.
    У Workspace может быть несколько интеграций.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="llm_integrations",
        help_text="Кто создал эту интеграцию и управляет ей",
    )

    name = models.CharField(
        max_length=255, help_text="Название интеграции, отображаемое пользователю"
    )

    provider = models.CharField(max_length=20, choices=LLMProvider.choices)

    # Универсальные поля для всех LLM
    base_url = models.URLField(
        blank=True,
        null=True,
        help_text="Базовый URL API. Для Ollama — http://localhost:11434",
    )

    api_key = models.CharField(
        max_length=512,
        blank=True,
        null=True,
        help_text="API ключ для OpenAI / DeepSeek. Для Ollama не нужен.",
    )

    model = models.CharField(
        max_length=255,
        help_text="Название модели, напр. 'gpt-4o', 'deepseek-chat', 'llama3'",
    )

    class Meta:
        verbose_name = "Интеграция LLM"
        verbose_name_plural = "Интеграции LLM"

    def __str__(self):
        return f"{self.get_provider_display()} ({self.name})"


class WorkspaceLLMIntegration(SimpleBaseModel):
    """
    Связь между Workspace и LLMIntegration.
    Говорит «эта интеграция доступна в этом воркспейсе».
    """

    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="llm_bindings",
    )

    integration = models.ForeignKey(
        LLMIntegration,
        on_delete=models.CASCADE,
        related_name="workspace_bindings",
    )

    # Можно сделать флаг «по умолчанию для этого workspace»
    is_default = models.BooleanField(default=False)

    class Meta:
        unique_together = ("workspace", "integration")
        verbose_name = "LLM-интеграция в workspace"
        verbose_name_plural = "LLM-интеграции в workspace"

    def __str__(self):
        return f"{self.workspace_id} -> {self.integration}"
