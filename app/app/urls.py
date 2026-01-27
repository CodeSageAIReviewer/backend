from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/users/", include("users.api.urls")),
    path("api/workspace/", include("code_hosts.api.urls.workspace")),
    path("api/llm/", include("llm.api.urls")),
]
