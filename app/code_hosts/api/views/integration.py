from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from code_hosts.api.permissions import (
    WorkspaceIntegrationDeletePermission,
    WorkspaceIntegrationModifyPermission,
    WorkspaceRepositoryDeletePermission,
)
from code_hosts.api.utils import format_datetime
from code_hosts.git_providers.factory import get_git_provider
from code_hosts.models.integration import CodeHostIntegration, CodeHostProvider
from code_hosts.models.merge_request import MergeRequest, MergeRequestState
from code_hosts.models.repository import Repository
from code_hosts.models.workspace import Workspace, WorkspaceMembership, WorkspaceRole
from code_hosts.tasks import sync_merge_requests

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


class WorkspaceIntegrationUpdateView(WorkspaceIntegrationBaseView):
    permission_classes = (IsAuthenticated, WorkspaceIntegrationModifyPermission)

    def patch(self, request, workspace_id, integration_id, *args, **kwargs):
        workspace = getattr(self, "workspace", None)
        if workspace is None:
            return Response(
                {"detail": "Workspace not found."}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            integration = CodeHostIntegration.objects.get(
                id=integration_id, workspace=workspace
            )
        except CodeHostIntegration.DoesNotExist:
            return Response(
                {"detail": "Integration not found in this workspace."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if "provider" in request.data:
            return Response(
                {"detail": "Field 'provider' cannot be modified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = request.data
        if "name" in data:
            name = data["name"]
            if not isinstance(name, str) or not (1 <= len(name) <= 255):
                return Response(
                    {"detail": "Invalid name length."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            integration.name = name

        if "base_url" in data:
            base_url = data["base_url"]
            if not isinstance(base_url, str) or not base_url:
                return Response(
                    {"detail": "Invalid base_url format."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            validator = URLValidator()
            try:
                validator(base_url)
            except ValidationError:
                return Response(
                    {"detail": "Invalid base_url format."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            integration.base_url = base_url

        if "access_token" in data:
            access_token = data["access_token"]
            if not isinstance(access_token, str) or not access_token:
                return Response(
                    {"detail": "Invalid access token."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            integration.access_token = access_token

        if "refresh_token" in data:
            refresh_token = data["refresh_token"]
            if refresh_token is not None and not isinstance(refresh_token, str):
                return Response(
                    {"detail": "Invalid refresh token."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            integration.refresh_token = refresh_token

        integration.save()

        return Response(
            {
                "id": integration.id,
                "workspace_id": workspace.id,
                "name": integration.name,
                "provider": integration.provider,
                "base_url": integration.base_url,
                "access_token_masked": "***********",
                "refresh_token_present": bool(integration.refresh_token),
                "updated_at": format_datetime(integration.updated_at),
            }
        )


class WorkspaceIntegrationDeleteView(WorkspaceIntegrationBaseView):
    permission_classes = (IsAuthenticated, WorkspaceIntegrationDeletePermission)

    def delete(self, request, workspace_id, integration_id, *args, **kwargs):
        workspace = getattr(self, "workspace", None)
        if workspace is None:
            return Response(
                {"detail": "Workspace not found."}, status=status.HTTP_404_NOT_FOUND
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

        integration.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


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


class WorkspaceRepositoryMergeRequestListView(WorkspaceIntegrationBaseView):
    def get(self, request, workspace_id, repository_id, *args, **kwargs):
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

        try:
            repository = Repository.objects.select_related("integration").get(
                id=repository_id, integration__workspace=workspace
            )
        except Repository.DoesNotExist:
            return Response(
                {"detail": "Repository not found."}, status=status.HTTP_404_NOT_FOUND
            )

        qs = MergeRequest.objects.filter(repository=repository)

        state = request.query_params.get("state")
        if state:
            normalized_state = state.strip().lower()
            valid_states = {choice.value for choice in MergeRequestState}
            if normalized_state not in valid_states:
                return Response(
                    {"detail": "Invalid state filter."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(state=normalized_state)

        search = request.query_params.get("search")
        if search:
            qs = qs.filter(title__icontains=search)

        title = request.query_params.get("title")
        if title:
            qs = qs.filter(title__icontains=title)

        branch = request.query_params.get("branch")
        if branch:
            qs = qs.filter(source_branch=branch)

        payload = []
        for mr in qs:
            payload.append(
                {
                    "id": mr.id,
                    "external_id": mr.external_id,
                    "iid": mr.iid,
                    "title": mr.title,
                    "description": mr.description,
                    "author_name": mr.author_name,
                    "author_username": mr.author_username,
                    "source_branch": mr.source_branch,
                    "target_branch": mr.target_branch,
                    "state": mr.state,
                    "web_url": mr.web_url,
                    "created_at": format_datetime(mr.created_at),
                    "updated_at": format_datetime(mr.updated_at),
                }
            )

        return Response(payload)


class WorkspaceRepositoryMergeRequestSyncView(WorkspaceIntegrationBaseView):
    def post(self, request, workspace_id, repository_id, *args, **kwargs):
        workspace, membership = self._get_workspace_and_membership(workspace_id)
        if workspace is None:
            return Response(
                {"detail": "Workspace not found."}, status=status.HTTP_404_NOT_FOUND
            )

        has_membership = membership is not None and membership.role in {
            WorkspaceRole.ADMIN,
            WorkspaceRole.MEMBER,
        }
        if not has_membership and workspace.owner_id != request.user.id:
            return Response(
                {"detail": "You do not have access to this repository."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            repository = Repository.objects.select_related("integration").get(
                id=repository_id, integration__workspace=workspace
            )
        except Repository.DoesNotExist:
            return Response(
                {"detail": "Repository not found."}, status=status.HTTP_404_NOT_FOUND
            )

        sync_merge_requests.delay(repository.id)

        return Response(
            {
                "status": "scheduled",
                "repository_id": repository.id,
                "task": "sync_merge_requests",
            }
        )


class WorkspaceRepositoryDeleteView(WorkspaceIntegrationBaseView):
    permission_classes = (IsAuthenticated, WorkspaceRepositoryDeletePermission)

    def delete(self, request, workspace_id, repository_id, *args, **kwargs):
        workspace = getattr(self, "workspace", None)
        if workspace is None:
            return Response(
                {"detail": "Workspace not found."}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            repository = Repository.objects.select_related("integration").get(
                id=repository_id, integration__workspace=workspace
            )
        except Repository.DoesNotExist:
            return Response(
                {"detail": "Repository not found."}, status=status.HTTP_404_NOT_FOUND
            )

        repository.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
