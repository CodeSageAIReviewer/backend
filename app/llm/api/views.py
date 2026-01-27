"""API views for the LLM app."""

from code_hosts.api.utils import format_datetime
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from llm.models import LLMIntegration, LLMProvider
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class LlmIntegrationBaseView(APIView):
    permission_classes = (IsAuthenticated,)

    def _get_integration(self, integration_id):
        try:
            return LLMIntegration.objects.get(
                id=integration_id, owner=self.request.user
            )
        except LLMIntegration.DoesNotExist:
            return None


class LlmIntegrationCreateView(LlmIntegrationBaseView):
    def post(self, request, *args, **kwargs):
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
                {"detail": "Provider is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(provider, str):
            return Response(
                {"detail": "Invalid provider."}, status=status.HTTP_400_BAD_REQUEST
            )

        provider = provider.strip().lower()
        if provider not in LLMProvider.values:
            return Response(
                {"detail": "Invalid provider."}, status=status.HTTP_400_BAD_REQUEST
            )

        model_name = request.data.get("model")
        if model_name is None:
            return Response(
                {"detail": "Model is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        if not isinstance(model_name, str) or not (1 <= len(model_name) <= 255):
            return Response(
                {"detail": "Invalid model length."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        base_url = request.data.get("base_url")
        if base_url in ("", None):
            base_url = None
        elif not isinstance(base_url, str):
            return Response(
                {"detail": "Invalid base_url format."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        else:
            validator = URLValidator()
            try:
                validator(base_url)
            except ValidationError:
                return Response(
                    {"detail": "Invalid base_url format."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        api_key = request.data.get("api_key")
        if provider in {LLMProvider.OPENAI, LLMProvider.DEEPSEEK}:
            if not isinstance(api_key, str) or not api_key:
                return Response(
                    {"detail": "API key is required for this provider."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            if api_key not in (None, ""):
                return Response(
                    {"detail": "API key is not required for this provider."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            api_key = None

        integration = LLMIntegration.objects.create(
            owner=request.user,
            name=name,
            provider=provider,
            base_url=base_url,
            api_key=api_key,
            model=model_name,
        )

        return Response(
            {
                "id": integration.id,
                "owner_id": integration.owner_id,
                "name": integration.name,
                "provider": integration.provider,
                "base_url": integration.base_url,
                "model": integration.model,
                "api_key_present": bool(integration.api_key),
                "created_at": format_datetime(integration.created_at),
            },
            status=status.HTTP_201_CREATED,
        )


class LlmIntegrationListView(LlmIntegrationBaseView):
    def get(self, request, *args, **kwargs):
        integrations = LLMIntegration.objects.filter(owner=request.user).order_by("id")

        payload = []
        for integration in integrations:
            payload.append(
                {
                    "id": integration.id,
                    "owner_id": integration.owner_id,
                    "name": integration.name,
                    "provider": integration.provider,
                    "base_url": integration.base_url,
                    "model": integration.model,
                    "api_key_present": bool(integration.api_key),
                    "created_at": format_datetime(integration.created_at),
                    "updated_at": format_datetime(integration.updated_at),
                }
            )

        return Response(payload)


class LlmIntegrationDetailView(LlmIntegrationBaseView):
    def get(self, request, integration_id, *args, **kwargs):
        integration = self._get_integration(integration_id)
        if integration is None:
            return Response(
                {"detail": "Integration not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "id": integration.id,
                "owner_id": integration.owner_id,
                "name": integration.name,
                "provider": integration.provider,
                "base_url": integration.base_url,
                "model": integration.model,
                "api_key_present": bool(integration.api_key),
                "created_at": format_datetime(integration.created_at),
                "updated_at": format_datetime(integration.updated_at),
            }
        )


class LlmIntegrationUpdateView(LlmIntegrationBaseView):
    def patch(self, request, integration_id, *args, **kwargs):
        integration = self._get_integration(integration_id)
        if integration is None:
            return Response(
                {"detail": "Integration not found."},
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

        if "model" in data:
            model_name = data["model"]
            if not isinstance(model_name, str) or not (1 <= len(model_name) <= 255):
                return Response(
                    {"detail": "Invalid model length."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            integration.model = model_name

        if "base_url" in data:
            base_url = data["base_url"]
            if base_url in ("", None):
                integration.base_url = None
            elif not isinstance(base_url, str):
                return Response(
                    {"detail": "Invalid base_url format."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            else:
                validator = URLValidator()
                try:
                    validator(base_url)
                except ValidationError:
                    return Response(
                        {"detail": "Invalid base_url format."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                integration.base_url = base_url

        if "api_key" in data:
            api_key = data["api_key"]
            if integration.provider in {LLMProvider.OPENAI, LLMProvider.DEEPSEEK}:
                if not isinstance(api_key, str) or not api_key:
                    return Response(
                        {"detail": "API key is required for this provider."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                integration.api_key = api_key
            else:
                if api_key not in (None, ""):
                    return Response(
                        {"detail": "API key is not required for this provider."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                integration.api_key = None

        integration.save()

        return Response(
            {
                "id": integration.id,
                "owner_id": integration.owner_id,
                "name": integration.name,
                "provider": integration.provider,
                "base_url": integration.base_url,
                "model": integration.model,
                "api_key_present": bool(integration.api_key),
                "updated_at": format_datetime(integration.updated_at),
            }
        )


class LlmIntegrationDeleteView(LlmIntegrationBaseView):
    def delete(self, request, integration_id, *args, **kwargs):
        integration = self._get_integration(integration_id)
        if integration is None:
            return Response(
                {"detail": "Integration not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        integration.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
