import json
import re
from dataclasses import dataclass
from typing import Any, Optional

from reviews.models import CommentSeverity, CommentType


@dataclass(frozen=True)
class ReviewCommentDraft:
    severity: str
    comment_type: str
    title: str
    body: str
    file_path: str = ""
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    suggestion: str = ""


@dataclass(frozen=True)
class ParsedReviewOutput:
    summary: str
    risk_level: str  # low|medium|high (строкой)
    comments: list[ReviewCommentDraft]
    raw_structured: dict[str, Any]


class ReviewOutputParser:
    """
    Парсер результата LLM.

    Ожидаемый формат structured_output:
    {
      "summary": "...",
      "risk_level": "low|medium|high",
      "comments": [{...}, ...]
    }

    Но парсер устойчив к:
    - JSON в raw_output, обёрнутый в ```json```
    - отсутствующим полям
    - кривым значениям severity/type
    """

    def parse(
        self, *, raw_output: str, structured_output: dict[str, Any]
    ) -> ParsedReviewOutput:
        data = structured_output or self._try_extract_json(raw_output) or {}

        summary = self._to_str(data.get("summary", "")).strip()
        risk_level = self._normalize_risk(self._to_str(data.get("risk_level", "low")))

        comments_raw = data.get("comments") or []
        if not isinstance(comments_raw, list):
            comments_raw = []

        drafts: list[ReviewCommentDraft] = []
        for item in comments_raw:
            if not isinstance(item, dict):
                continue

            severity = self._normalize_severity(
                self._to_str(item.get("severity", CommentSeverity.INFO))
            )
            comment_type = self._normalize_type(
                self._to_str(item.get("type", CommentType.GENERAL))
            )

            title = self._to_str(item.get("title", "")).strip()
            body = self._to_str(item.get("body", "")).strip()

            if not body:
                # Без тела комментарий бессмысленен
                continue

            file_path = self._to_str(item.get("file_path", "")).strip()

            line_start = self._to_int_or_none(item.get("line_start"))
            line_end = self._to_int_or_none(item.get("line_end"))
            if line_start is not None and line_end is None:
                line_end = line_start

            suggestion = self._to_str(item.get("suggestion", "")).strip()

            drafts.append(
                ReviewCommentDraft(
                    severity=severity,
                    comment_type=comment_type,
                    title=title,
                    body=body,
                    file_path=file_path,
                    line_start=line_start,
                    line_end=line_end,
                    suggestion=suggestion,
                )
            )

        return ParsedReviewOutput(
            summary=summary,
            risk_level=risk_level,
            comments=drafts,
            raw_structured=data if isinstance(data, dict) else {},
        )

    # -------------------------
    # helpers
    # -------------------------

    def _try_extract_json(self, raw: str) -> dict[str, Any] | None:
        raw = (raw or "").strip()
        if not raw:
            return None

        # Частый случай: ```json ... ```
        cleaned = raw
        if "```" in cleaned:
            cleaned = cleaned.replace("```json", "").replace("```", "").strip()

        # Иногда есть текст до/после JSON — попробуем вытащить первый JSON-объект
        obj_text = self._extract_first_json_object(cleaned)
        if not obj_text:
            return None

        try:
            parsed = json.loads(obj_text)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None

    def _extract_first_json_object(self, text: str) -> str | None:
        """
        Находит первый JSON object {...} в тексте, устойчиво к мусору вокруг.
        """
        # Быстрый путь: если строка уже выглядит как объект
        stripped = text.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            return stripped

        # Иначе попробуем найти сбалансированные фигурные скобки
        start = stripped.find("{")
        if start == -1:
            return None

        depth = 0
        for i in range(start, len(stripped)):
            if stripped[i] == "{":
                depth += 1
            elif stripped[i] == "}":
                depth -= 1
                if depth == 0:
                    return stripped[start : i + 1]
        return None

    def _normalize_severity(self, value: str) -> str:
        v = (value or "").strip().lower()
        allowed = {c.value for c in CommentSeverity}
        if v in allowed:
            return v
        # популярные синонимы
        if v in {"warn", "warning"}:
            return CommentSeverity.WARNING
        if v in {"err", "error", "critical"}:
            return CommentSeverity.ERROR
        return CommentSeverity.INFO

    def _normalize_type(self, value: str) -> str:
        v = (value or "").strip().lower()
        allowed = {c.value for c in CommentType}
        if v in allowed:
            return v
        # синонимы/ошибки модели
        mapping = {
            "codesmell": CommentType.CODE_SMELL,
            "code-smell": CommentType.CODE_SMELL,
            "sec": CommentType.SECURITY,
            "perf": CommentType.PERFORMANCE,
            "doc": CommentType.DOCUMENTATION,
        }
        return mapping.get(v, CommentType.GENERAL)

    def _normalize_risk(self, value: str) -> str:
        v = (value or "").strip().lower()
        if v in {"low", "medium", "high"}:
            return v
        return "low"

    def _to_str(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value)

    def _to_int_or_none(self, value: Any) -> Optional[int]:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except Exception:
            return None
