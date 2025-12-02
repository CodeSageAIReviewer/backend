from django.db import models

from code_hosts.models.commit_author import CommitAuthor
from code_hosts.models.repository import Repository
from common.models import SimpleBaseModel


class Commit(SimpleBaseModel):
    repository = models.ForeignKey(
        Repository, on_delete=models.CASCADE, related_name="commits"
    )

    hash = models.CharField(max_length=64, db_index=True)

    author = models.ForeignKey(
        CommitAuthor, on_delete=models.SET_NULL, null=True, related_name="commits"
    )

    message = models.TextField()
    authored_date = models.DateTimeField()

    class Meta:
        unique_together = ("repository", "hash")
        ordering = ["-authored_date"]
        verbose_name = "Коммит"
        verbose_name_plural = "Коммиты"

    def __str__(self):
        return f"{self.hash[:8]} - {self.message[:50]}"
