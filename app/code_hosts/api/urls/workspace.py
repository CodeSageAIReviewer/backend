from django.urls import path

from code_hosts.api.views.integration import (
    WorkspaceIntegrationAvailableRepositoriesView,
    WorkspaceIntegrationCreateView,
    WorkspaceIntegrationDeleteView,
    WorkspaceIntegrationListView,
    WorkspaceIntegrationUpdateView,
    WorkspaceRepositoryConnectView,
    WorkspaceRepositoryDeleteView,
    WorkspaceRepositoryListView,
)
from code_hosts.api.views.workspace import (
    WorkspaceCreateView,
    WorkspaceDeleteView,
    WorkspaceListView,
    WorkspaceUpdateView,
)

urlpatterns = [
    path("create/", WorkspaceCreateView.as_view(), name="workspace-create"),
    path("list/", WorkspaceListView.as_view(), name="workspace-list"),
    path(
        "<int:workspace_id>/delete/",
        WorkspaceDeleteView.as_view(),
        name="workspace-delete",
    ),
    path(
        "<int:workspace_id>/update/",
        WorkspaceUpdateView.as_view(),
        name="workspace-update",
    ),
    # Integration URLs
    path(
        "<int:workspace_id>/integrations/create/",
        WorkspaceIntegrationCreateView.as_view(),
        name="workspace-integration-create",
    ),
    path(
        "<int:workspace_id>/integrations/list/",
        WorkspaceIntegrationListView.as_view(),
        name="workspace-integration-list",
    ),
    path(
        "<int:workspace_id>/integrations/<int:integration_id>/repositories/available/",
        WorkspaceIntegrationAvailableRepositoriesView.as_view(),
        name="workspace-integration-repositories-available",
    ),
    path(
        "<int:workspace_id>/integrations/<int:integration_id>/update/",
        WorkspaceIntegrationUpdateView.as_view(),
        name="workspace-integration-update",
    ),
    path(
        "<int:workspace_id>/integrations/<int:integration_id>/delete/",
        WorkspaceIntegrationDeleteView.as_view(),
        name="workspace-integration-delete",
    ),
    path(
        "<int:workspace_id>/repositories/connect/",
        WorkspaceRepositoryConnectView.as_view(),
        name="workspace-repositories-connect",
    ),
    path(
        "<int:workspace_id>/repositories/list/",
        WorkspaceRepositoryListView.as_view(),
        name="workspace-repositories-list",
    ),
    path(
        "<int:workspace_id>/repositories/<int:repository_id>/delete/",
        WorkspaceRepositoryDeleteView.as_view(),
        name="workspace-repositories-delete",
    ),
]
