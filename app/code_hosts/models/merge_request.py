from django.db import models

from code_hosts.models.repository import Repository
from common.models import SimpleBaseModel


class MergeRequestState(models.TextChoices):
    OPEN = "open", "Open"
    CLOSED = "closed", "Closed"
    MERGED = "merged", "Merged"


class MergeRequest(SimpleBaseModel):
    repository = models.ForeignKey(
        Repository, on_delete=models.CASCADE, related_name="merge_requests"
    )

    external_id = models.CharField(max_length=255, help_text="ID MR/PR в GitLab/GitHub")
    iid = models.CharField(
        max_length=50, help_text="Номер MR в проекте (IID / номер PR)"
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    author_name = models.CharField(max_length=255)
    author_username = models.CharField(max_length=255, blank=True)

    source_branch = models.CharField(max_length=255)
    target_branch = models.CharField(max_length=255)

    state = models.CharField(max_length=20, choices=MergeRequestState.choices)
    web_url = models.URLField()

    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        unique_together = ("repository", "external_id")
        ordering = ["-created_at"]
        verbose_name = "Merge Request / Pull Request"
        verbose_name_plural = "Merge Requests / Pull Requests"

    def __str__(self):
        return f"!{self.iid}: {self.title}"
