from django.urls import path

from .views import LlmPingView

urlpatterns = [
    path("ping/", LlmPingView.as_view(), name="llm-ping"),
]
