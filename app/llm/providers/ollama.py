# llm/providers/ollama.py
from langchain_community.chat_models import ChatOllama
from llm.providers.base import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    def _build_chat_model(self) -> ChatOllama:
        return ChatOllama(
            model=self.integration.model,
            base_url=self.integration.base_url or "http://localhost:11434",
        )
