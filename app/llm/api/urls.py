from django.urls import path

from .views import (
    LlmIntegrationCreateView,
    LlmIntegrationDeleteView,
    LlmIntegrationDetailView,
    LlmIntegrationListView,
    LlmIntegrationUpdateView,
)

urlpatterns = [
    path(
        "integrations/create/",
        LlmIntegrationCreateView.as_view(),
        name="llm-integration-create",
    ),
    path(
        "integrations/list/",
        LlmIntegrationListView.as_view(),
        name="llm-integration-list",
    ),
    path(
        "integrations/<int:integration_id>/detail/",
        LlmIntegrationDetailView.as_view(),
        name="llm-integration-detail",
    ),
    path(
        "integrations/<int:integration_id>/update/",
        LlmIntegrationUpdateView.as_view(),
        name="llm-integration-update",
    ),
    path(
        "integrations/<int:integration_id>/delete/",
        LlmIntegrationDeleteView.as_view(),
        name="llm-integration-delete",
    ),
]
