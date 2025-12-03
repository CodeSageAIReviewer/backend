from langchain_openai import ChatOpenAI

from llm.providers.base import BaseLLMProvider


class OpenAIChatGPTProvider(BaseLLMProvider):
    def _build_chat_model(self) -> ChatOpenAI:
        return ChatOpenAI(
            model=self.integration.model,
            api_key=self.integration.api_key,
            base_url=self.integration.base_url or None,
        )
