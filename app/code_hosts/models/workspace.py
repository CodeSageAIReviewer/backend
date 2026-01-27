from common.models import SimpleBaseModel
from django.db import models
from users.models import User


class Workspace(SimpleBaseModel):
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="owned_workspaces"
    )


class WorkspaceRole(models.TextChoices):
    ADMIN = "admin", "Admin"
    MEMBER = "member", "Member"
    VIEWER = "viewer", "Viewer"


class WorkspaceMembership(SimpleBaseModel):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    role = models.CharField(
        max_length=20, choices=WorkspaceRole.choices, default=WorkspaceRole.MEMBER
    )

    class Meta:
        unique_together = ("workspace", "user")
