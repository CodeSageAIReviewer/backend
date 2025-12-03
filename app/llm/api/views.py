"""API views for the LLM app."""

from rest_framework.response import Response
from rest_framework.views import APIView


class LlmPingView(APIView):
    def get(self, request):
        return Response({"status": "ok"})
