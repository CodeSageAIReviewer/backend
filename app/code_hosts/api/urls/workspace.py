from django.urls import path

from code_hosts.api.views.workspace import WorkspaceCreateView, WorkspaceListView

urlpatterns = [
    path("create/", WorkspaceCreateView.as_view(), name="workspace-create"),
    path("list/", WorkspaceListView.as_view(), name="workspace-list"),
]
