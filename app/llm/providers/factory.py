from llm.models import LLMProvider
from llm.providers.deepseek import DeepSeekProvider
from llm.providers.ollama import OllamaProvider
from llm.providers.openai_chatgpt import OpenAIChatGPTProvider


def get_llm_provider(integration: LLMProvider) -> object:
    if integration.provider == LLMProvider.OPENAI:
        return OpenAIChatGPTProvider(integration)
    if integration.provider == LLMProvider.DEEPSEEK:
        return DeepSeekProvider(integration)
    if integration.provider == LLMProvider.OLLAMA:
        return OllamaProvider(integration)
    raise ValueError(f"Unsupported provider: {integration.provider}")
