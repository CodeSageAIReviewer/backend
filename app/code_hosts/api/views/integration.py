from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from code_hosts.api.utils import format_datetime
from code_hosts.git_providers.factory import get_git_provider
from code_hosts.models.integration import CodeHostIntegration, CodeHostProvider
from code_hosts.models.workspace import Workspace, WorkspaceMembership, WorkspaceRole

PROVIDER_DEFAULT_URLS = {
    CodeHostProvider.GITLAB: "https://gitlab.com",
    CodeHostProvider.GITHUB: "https://api.github.com",
}


class WorkspaceIntegrationBaseView(APIView):
    permission_classes = (IsAuthenticated,)

    def _get_workspace_and_membership(self, workspace_id):
        try:
            workspace = Workspace.objects.get(id=workspace_id)
        except Workspace.DoesNotExist:
            return None, None

        membership = WorkspaceMembership.objects.filter(
            workspace=workspace, user=self.request.user
        ).first()
        return workspace, membership


class WorkspaceIntegrationCreateView(WorkspaceIntegrationBaseView):
    def post(self, request, workspace_id, *args, **kwargs):
        workspace, membership = self._get_workspace_and_membership(workspace_id)
        if workspace is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if membership is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if membership.role != WorkspaceRole.ADMIN:
            return Response(
                {
                    "detail": "You do not have permission to add integrations to this workspace."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        name = request.data.get("name")
        if name is None:
            return Response(
                {"detail": "Name is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        if not isinstance(name, str) or not (1 <= len(name) <= 255):
            return Response(
                {"detail": "Invalid name length."}, status=status.HTTP_400_BAD_REQUEST
            )

        provider = request.data.get("provider")
        if provider is None:
            return Response(
                {"detail": "Provider is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        if not isinstance(provider, str):
            return Response(
                {"detail": "Invalid provider."}, status=status.HTTP_400_BAD_REQUEST
            )

        provider = provider.strip().lower()
        if provider not in PROVIDER_DEFAULT_URLS:
            return Response(
                {"detail": "Invalid provider."}, status=status.HTTP_400_BAD_REQUEST
            )

        access_token = request.data.get("access_token")
        if access_token is None:
            return Response(
                {"detail": "Access token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(access_token, str) or not access_token:
            return Response(
                {"detail": "Invalid access token."}, status=status.HTTP_400_BAD_REQUEST
            )

        provided_base_url = request.data.get("base_url")
        if (
            provided_base_url is not None
            and provided_base_url != ""
            and not isinstance(provided_base_url, str)
        ):
            return Response(
                {"detail": "Invalid base URL."}, status=status.HTTP_400_BAD_REQUEST
            )

        base_url = (
            provided_base_url
            if isinstance(provided_base_url, str) and provided_base_url != ""
            else PROVIDER_DEFAULT_URLS[provider]
        )

        refresh_token = request.data.get("refresh_token")
        if refresh_token is not None and not isinstance(refresh_token, str):
            return Response(
                {"detail": "Invalid refresh token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            integration = CodeHostIntegration.objects.create(
                workspace=workspace,
                name=name,
                provider=provider,
                base_url=base_url,
                access_token=access_token,
                refresh_token=refresh_token,
            )

        return Response(
            {
                "id": integration.id,
                "workspace_id": workspace.id,
                "name": integration.name,
                "provider": integration.provider,
                "base_url": integration.base_url,
                "created_at": format_datetime(integration.created_at),
            },
            status=status.HTTP_201_CREATED,
        )


class WorkspaceIntegrationListView(WorkspaceIntegrationBaseView):
    def get(self, request, workspace_id, *args, **kwargs):
        workspace, membership = self._get_workspace_and_membership(workspace_id)
        if workspace is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if membership is None:
            return Response(
                {"detail": "You do not have access to this workspace."},
                status=status.HTTP_403_FORBIDDEN,
            )

        integrations = CodeHostIntegration.objects.filter(workspace=workspace).order_by(
            "id"
        )

        payload = []
        for integration in integrations:
            payload.append(
                {
                    "id": integration.id,
                    "name": integration.name,
                    "provider": integration.provider,
                    "base_url": integration.base_url,
                    "created_at": format_datetime(integration.created_at),
                }
            )

        return Response(payload)


class WorkspaceIntegrationAvailableRepositoriesView(WorkspaceIntegrationBaseView):
    def get(self, request, workspace_id, integration_id, *args, **kwargs):
        workspace, membership = self._get_workspace_and_membership(workspace_id)
        if workspace is None:
            return []

        if membership is None:
            return Response(
                {"detail": "You do not have access to this workspace."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            integration = CodeHostIntegration.objects.get(
                id=integration_id, workspace=workspace
            )
        except CodeHostIntegration.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        provider = get_git_provider(integration)
        repositories = provider.list_repositories()

        payload = []
        for repository in repositories:
            payload.append(
                {
                    "external_id": repository.external_id,
                    "name": repository.name,
                    "full_path": repository.full_path,
                    "default_branch": repository.default_branch,
                    "provider": integration.provider,
                    "web_url": repository.web_url,
                }
            )

        return Response(payload)
