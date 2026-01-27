import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

from code_hosts.models.merge_request import MergeRequest
from llm.models import LLMIntegration
from llm.providers.factory import get_llm_provider
from reviews.exceptions import LLMCallError
from reviews.prompts.review_prompts import build_review_prompt

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMReviewResult:
    raw_output: str
    structured_output: dict[str, Any]


class LLMReviewService:
    """
    Сервис, который:
    - собирает промпт
    - вызывает LLM (через LangChain провайдер)
    - пытается распарсить JSON (structured_output)
    """

    def run_review(
        self,
        *,
        mr: MergeRequest,
        llm_integration: LLMIntegration,
        diff_text: str,
        language: str = "ru",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMReviewResult:
        try:
            provider = get_llm_provider(llm_integration)
        except Exception as exc:
            logger.exception(
                "LLM provider resolution failed",
                extra={
                    "mr_id": mr.pk,
                    "llm_integration_id": llm_integration.pk,
                    "provider": llm_integration.provider,
                    "model": getattr(llm_integration, "model", None)
                    or getattr(llm_integration, "default_model", None),
                },
            )
            raise LLMCallError(str(exc)) from exc

        prompt = build_review_prompt(
            repo_full_path=mr.repository.full_path,
            mr_iid=str(mr.iid),
            mr_title=mr.title,
            mr_description=mr.description or "",
            source_branch=mr.source_branch,
            target_branch=mr.target_branch,
            diff_text=diff_text,
            language=language,
        )

        invoke_kwargs = {}
        # LangChain ChatModel принимает model_kwargs по-разному в разных интеграциях,
        # поэтому здесь безопаснее оставлять пустым и управлять параметрами на уровне провайдера.
        # Но на будущее можно прокинуть temperature/max_tokens если провайдер это поддержит.
        if temperature is not None:
            invoke_kwargs["temperature"] = temperature
        if max_tokens is not None:
            invoke_kwargs["max_tokens"] = max_tokens

        try:
            raw = provider.generate(
                prompt.user,
                system_prompt=prompt.system,
                **invoke_kwargs,
            )
        except Exception as exc:
            logger.exception(
                "LLM call failed",
                extra={
                    "mr_id": mr.pk,
                    "llm_integration_id": llm_integration.pk,
                    "provider": llm_integration.provider,
                    "model": getattr(llm_integration, "model", None)
                    or getattr(llm_integration, "default_model", None),
                },
            )
            raise LLMCallError(str(exc)) from exc

        structured = self._safe_parse_json(raw)

        return LLMReviewResult(raw_output=raw, structured_output=structured)

    def _safe_parse_json(self, raw: str) -> dict[str, Any]:
        """
        Пытаемся распарсить JSON. Если LLM вернула мусор — возвращаем пустую структуру
        и оставляем raw_output для отладки/повторного парсинга.
        """
        raw_stripped = raw.strip()
        try:
            return json.loads(raw_stripped)
        except Exception:
            # Частый кейс: модель оборачивает JSON в ```json ... ```
            if "```" in raw_stripped:
                cleaned = raw_stripped.replace("```json", "").replace("```", "").strip()
                try:
                    return json.loads(cleaned)
                except Exception:
                    return {}
            return {}
