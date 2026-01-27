from langchain_openai import ChatOpenAI
from llm.providers.base import BaseLLMProvider


class DeepSeekProvider(BaseLLMProvider):
    """
    Провайдер для DeepSeek, использующий OpenAI-совместимый Chat API.

    Ожидается, что в LLMIntegration:
      - provider = "deepseek"
      - api_key  = ключ DeepSeek
      - model = например, "deepseek-chat" или "deepseek-coder"
      - base_url (опционально) — если не задан, используется дефолтный URL DeepSeek.
    """

    DEFAULT_BASE_URL = "https://api.deepseek.com"

    def _build_chat_model(self) -> ChatOpenAI:
        return ChatOpenAI(
            model=self.integration.model,
            api_key=self.integration.api_key,
            base_url=self.integration.base_url or self.DEFAULT_BASE_URL,
        )
