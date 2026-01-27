from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, List, Optional, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from llm.models import LLMIntegration  # путь поправь под свой проект


class BaseLLMProvider(ABC):
    """
    Базовый провайдер для работы с LLM через LangChain.

    Наследники должны реализовать метод `_build_chat_model`,
    который возвращает конкретную ChatModel (OpenAI, DeepSeek, Ollama и т.п.).
    """

    def __init__(self, integration: LLMIntegration):
        self.integration = integration
        self._chat_model: BaseChatModel = self._build_chat_model()

    # ----------------------------------------------------------------------
    # Абстрактная часть: конкретные провайдеры
    # ----------------------------------------------------------------------
    @abstractmethod
    def _build_chat_model(self) -> BaseChatModel:
        """
        Собирает и возвращает LangChain ChatModel для конкретного провайдера.

        Пример для OpenAI (в наследнике):

            from langchain_openai import ChatOpenAI

            def _build_chat_model(self) -> BaseChatModel:
                return ChatOpenAI(
                    model=self.integration.model,
                    api_key=self.integration.api_key,
                    base_url=self.integration.base_url or None,
                    temperature=0.1,
                )
        """
        raise NotImplementedError

    # ----------------------------------------------------------------------
    # Публичные методы для генерации
    # ----------------------------------------------------------------------
    def generate(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        **invoke_kwargs,
    ) -> str:
        """
        Простой способ получить ответ от модели по текстовому промпту.

        - system_prompt (опционально) задаёт роль/поведение модели.
        - invoke_kwargs передаются напрямую в .invoke() LangChain модели.
        """

        messages: List[BaseMessage] = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))

        response = self._chat_model.invoke(messages, **invoke_kwargs)
        # У ChatModel обычно есть .content
        return getattr(response, "content", str(response))

    def generate_messages(
        self,
        messages: Sequence[BaseMessage],
        **invoke_kwargs,
    ) -> BaseMessage:
        """
        Низкоуровневый метод: принимает список LangChain-сообщений и
        возвращает одно итоговое сообщение (ответ модели).
        """

        return self._chat_model.invoke(list(messages), **invoke_kwargs)

    def stream(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        **stream_kwargs,
    ) -> Iterable[str]:
        """
        Стриминговая генерация — отдаёт чанки текста по мере прихода.
        """

        messages: List[BaseMessage] = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))

        for chunk in self._chat_model.stream(messages, **stream_kwargs):
            # chunk — это ChatMessageChunk / AIMessageChunk
            content = getattr(chunk, "content", None)
            if content:
                yield content

    # ----------------------------------------------------------------------
    # Хелперы / возможности для расширения
    # ----------------------------------------------------------------------
    def get_underlying_model(self) -> BaseChatModel:
        """
        Возвращает низкоуровневую LangChain-модель, если нужно использовать
        её напрямую (например, для сложных Chain'ов).
        """
        return self._chat_model

    def get_model_info(self) -> dict:
        """
        Базовая информация о модели/провайдере.
        Наследники могут переопределить, чтобы вернуть что-то своё.
        """
        return {
            "provider": self.integration.provider,
            "model": self.integration.model,
            "base_url": self.integration.base_url,
            "name": self.integration.name,
        }
