from django.urls import path

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
]
