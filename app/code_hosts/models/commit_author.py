from common.models import SimpleBaseModel
from django.db import models


class CommitAuthor(SimpleBaseModel):
    """
    Автор коммитов (нормализованная сущность).
    Может быть как локальным разработчиком, так и внешним.
    """

    name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("name", "email")
        verbose_name = "Автор коммитов"
        verbose_name_plural = "Авторы коммитов"

    def __str__(self):
        return f"{self.name} <{self.email}>"
