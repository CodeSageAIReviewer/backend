from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission

from code_hosts.models.workspace import Workspace, WorkspaceMembership, WorkspaceRole


class WorkspaceAdminOrOwnerPermission(BasePermission):
    """
    Grants access if the requesting user owns the workspace or has the admin role.
    Sets `workspace` and `workspace_membership` on the view for downstream use.
    """

    message = "You do not have permission to access this workspace."
    workspace_kwarg = "workspace_id"

    def has_permission(self, request, view):
        workspace_id = view.kwargs.get(self.workspace_kwarg)
        if workspace_id is None:
            return False

        try:
            workspace = Workspace.objects.get(id=workspace_id)
        except Workspace.DoesNotExist:
            raise NotFound(detail="Workspace not found.")

        membership = WorkspaceMembership.objects.filter(
            workspace=workspace, user=request.user
        ).first()

        is_owner = workspace.owner_id == request.user.id
        has_admin_role = (
            membership is not None and membership.role == WorkspaceRole.ADMIN
        )

        if not is_owner and not has_admin_role:
            return False

        view.workspace = workspace
        view.workspace_membership = membership
        return True


class WorkspaceModifyPermission(WorkspaceAdminOrOwnerPermission):
    message = "You do not have permission to modify this workspace."


class WorkspaceDeletePermission(WorkspaceAdminOrOwnerPermission):
    message = "Workspace deletion is restricted."


class WorkspaceIntegrationModifyPermission(WorkspaceAdminOrOwnerPermission):
    message = "You do not have permission to modify this integration."


class WorkspaceIntegrationDeletePermission(WorkspaceAdminOrOwnerPermission):
    message = "You do not have permission to delete this integration."


class WorkspaceRepositoryDeletePermission(WorkspaceAdminOrOwnerPermission):
    message = "You do not have permission to delete repositories in this workspace."
