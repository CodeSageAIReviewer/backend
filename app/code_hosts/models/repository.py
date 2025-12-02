from django.db import models

from code_hosts.models.integration import CodeHostIntegration
from common.models import SimpleBaseModel


class Repository(SimpleBaseModel):
    integration = models.ForeignKey(
        CodeHostIntegration, on_delete=models.CASCADE, related_name="repositories"
    )

    external_id = models.CharField(
        max_length=255, help_text="ID репозитория в GitLab/GitHub"
    )

    name = models.CharField(max_length=255)
    full_path = models.CharField(max_length=512, help_text="namespace/project_name")

    default_branch = models.CharField(max_length=255, default="main")
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("integration", "external_id")
        verbose_name = "Репозиторий"
        verbose_name_plural = "Репозитории"

    def __str__(self):
        return self.full_path
