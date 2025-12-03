from django.urls import path

from code_hosts.api.views.integration import (
    WorkspaceIntegrationAvailableRepositoriesView,
    WorkspaceIntegrationCreateView,
    WorkspaceIntegrationListView,
)
from code_hosts.api.views.workspace import (
    WorkspaceCreateView,
    WorkspaceDeleteView,
    WorkspaceListView,
)

urlpatterns = [
    path("create/", WorkspaceCreateView.as_view(), name="workspace-create"),
    path("list/", WorkspaceListView.as_view(), name="workspace-list"),
    path(
        "<int:workspace_id>/delete/",
        WorkspaceDeleteView.as_view(),
        name="workspace-delete",
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
]
