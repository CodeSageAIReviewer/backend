from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from code_hosts.api.utils import format_datetime
from code_hosts.git_providers.factory import get_git_provider
from code_hosts.models.integration import CodeHostIntegration, CodeHostProvider
from code_hosts.models.repository import Repository
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


class WorkspaceRepositoryConnectView(WorkspaceIntegrationBaseView):
    def post(self, request, workspace_id, *args, **kwargs):
        workspace, membership = self._get_workspace_and_membership(workspace_id)
        if workspace is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if membership is None:
            return Response(
                {"detail": "You do not have access to this workspace."},
                status=status.HTTP_403_FORBIDDEN,
            )

        integration_id = request.data.get("integration_id")
        if integration_id is None:
            return Response(
                {"detail": "integration_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(integration_id, int):
            try:
                integration_id = int(integration_id)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "integration_id is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            integration = CodeHostIntegration.objects.get(
                id=integration_id, workspace=workspace
            )
        except CodeHostIntegration.DoesNotExist:
            return Response(
                {"detail": "Integration not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        repositories = request.data.get("repositories")
        if not isinstance(repositories, list) or not repositories:
            return Response(
                {"detail": "repositories must be a non-empty array."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        saved_repositories = []
        with transaction.atomic():
            for repository_data in repositories:
                if not isinstance(repository_data, dict):
                    return Response(
                        {"detail": "Each repository must be an object."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                external_id = repository_data.get("external_id")
                name = repository_data.get("name")
                full_path = repository_data.get("full_path")
                default_branch = repository_data.get("default_branch")

                if not isinstance(external_id, str) or not external_id:
                    return Response(
                        {"detail": "external_id is required for each repository."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                if not isinstance(name, str) or not name:
                    return Response(
                        {"detail": "name is required for each repository."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                if not isinstance(full_path, str) or not full_path:
                    return Response(
                        {"detail": "full_path is required for each repository."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                if default_branch is None or default_branch == "":
                    default_branch = "main"
                elif not isinstance(default_branch, str):
                    return Response(
                        {"detail": "default_branch must be a string."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                repository, _ = Repository.objects.update_or_create(
                    integration=integration,
                    external_id=external_id,
                    defaults={
                        "name": name,
                        "full_path": full_path,
                        "default_branch": default_branch,
                    },
                )

                saved_repositories.append(repository)

        payload = {
            "saved": len(saved_repositories),
            "repositories": [],
        }
        for repository in saved_repositories:
            payload["repositories"].append(
                {
                    "id": repository.id,
                    "external_id": repository.external_id,
                    "name": repository.name,
                    "full_path": repository.full_path,
                    "default_branch": repository.default_branch,
                    "last_synced_at": (
                        format_datetime(repository.last_synced_at)
                        if repository.last_synced_at
                        else None
                    ),
                }
            )

        return Response(payload)


class WorkspaceRepositoryListView(WorkspaceIntegrationBaseView):
    def get(self, request, workspace_id, *args, **kwargs):
        workspace, membership = self._get_workspace_and_membership(workspace_id)
        if workspace is None:
            return Response(
                {"detail": "Workspace not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if membership is None:
            return Response(
                {"detail": "You do not have access to this workspace."},
                status=status.HTTP_403_FORBIDDEN,
            )

        repositories = (
            Repository.objects.filter(integration__workspace=workspace)
            .select_related("integration")
            .order_by("id")
        )

        payload = []
        for repository in repositories:
            payload.append(
                {
                    "id": repository.id,
                    "integration_id": repository.integration_id,
                    "external_id": repository.external_id,
                    "name": repository.name,
                    "full_path": repository.full_path,
                    "default_branch": repository.default_branch,
                    "last_synced_at": (
                        format_datetime(repository.last_synced_at)
                        if repository.last_synced_at
                        else None
                    ),
                }
            )

        return Response(payload)
