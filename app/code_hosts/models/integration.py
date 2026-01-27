from common.models import SimpleBaseModel
from django.db import models


class CodeHostProvider(models.TextChoices):
    GITLAB = "gitlab", "GitLab"
    GITHUB = "github", "GitHub"


class CodeHostIntegration(SimpleBaseModel):
    """
    Хранит подключение пользователя к хостингу кода:
    GitLab, GitHub и т.д.
    """

    workspace = models.ForeignKey(
        "code_hosts.Workspace", on_delete=models.CASCADE, related_name="integrations"
    )

    name = models.CharField(
        max_length=255, help_text="Название интеграции, отображаемое пользователю"
    )
    provider = models.CharField(max_length=20, choices=CodeHostProvider.choices)

    base_url = models.URLField(
        default="https://gitlab.com",
        help_text="Базовый URL сервера (для self-hosted GitLab)",
    )

    access_token = models.CharField(max_length=255)
    refresh_token = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Интеграция с Git-сервисом"
        verbose_name_plural = "Интеграции с Git-сервисами"

    def __str__(self):
        return f"{self.get_provider_display()} ({self.name})"
