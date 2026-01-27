from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from users.api.views import UserRegisterView, UserTokenObtainPairView

urlpatterns = [
    path("register/", UserRegisterView.as_view(), name="user-register"),
    path("login/", UserTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
