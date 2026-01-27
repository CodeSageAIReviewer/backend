from code_hosts.api.permissions import (
    WorkspaceDeletePermission,
    WorkspaceModifyPermission,
)
from code_hosts.api.utils import format_datetime
from code_hosts.models.workspace import Workspace, WorkspaceMembership, WorkspaceRole
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class WorkspaceCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        name = request.data.get("name")
        if name is None:
            return Response(
                {"detail": "Name is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        if not isinstance(name, str) or not (1 <= len(name) <= 255):
            return Response(
                {"detail": "Invalid name length."}, status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            workspace = Workspace.objects.create(name=name, owner=request.user)
            membership = WorkspaceMembership.objects.create(
                workspace=workspace,
                user=request.user,
                role=WorkspaceRole.ADMIN,
            )

        return Response(
            {
                "id": workspace.id,
                "name": workspace.name,
                "owner_id": workspace.owner_id,
                "created_at": format_datetime(workspace.created_at),
                "role": membership.role,
            },
            status=status.HTTP_201_CREATED,
        )


class WorkspaceListView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        memberships = (
            WorkspaceMembership.objects.select_related("workspace")
            .filter(user=request.user)
            .order_by("workspace__id")
        )

        payload = []
        for membership in memberships:
            workspace = membership.workspace
            payload.append(
                {
                    "id": workspace.id,
                    "name": workspace.name,
                    "owner_id": workspace.owner_id,
                    "role": membership.role,
                    "created_at": format_datetime(workspace.created_at),
                }
            )

        return Response(payload)


class WorkspaceDeleteView(APIView):
    permission_classes = (IsAuthenticated, WorkspaceDeletePermission)

    def delete(self, request, workspace_id, *args, **kwargs):
        workspace = getattr(self, "workspace", None)
        if workspace is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        workspace.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspaceUpdateView(APIView):
    permission_classes = (IsAuthenticated, WorkspaceModifyPermission)

    def patch(self, request, workspace_id, *args, **kwargs):
        workspace = getattr(self, "workspace", None)
        if workspace is None:
            return Response(
                {"detail": "Workspace not found."}, status=status.HTTP_404_NOT_FOUND
            )

        data = request.data
        if "name" in data:
            name = data.get("name")
            if not isinstance(name, str) or not (1 <= len(name) <= 255):
                return Response(
                    {"detail": "Invalid name length."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            workspace.name = name

        workspace.save()

        return Response(
            {
                "id": workspace.id,
                "name": workspace.name,
                "owner_id": workspace.owner_id,
                "updated_at": format_datetime(workspace.updated_at),
            }
        )
