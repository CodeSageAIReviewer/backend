from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

SEVERITY_META = {
    "error": {"icon": "❌", "label": "Bug"},
    "warning": {"icon": "⚠️", "label": "Warning"},
    "info": {"icon": "ℹ️", "label": "Info"},
}

TYPE_META = {
    "bug": "Bug",
    "security": "Security",
    "code_smell": "Code Smell",
    "tests": "Tests",
    "style": "Style",
    "documentation": "Documentation",
    "performance": "Performance",
}


RISK_LEVEL_META = {
    "low": "🟢 Low",
    "medium": "🟡 Medium",
    "high": "🔴 High",
}


class MarkdownReviewRenderer:
    def render(self, structured: Dict[str, Any]) -> str:
        parts: List[str] = []

        parts.append(self._render_header())
        parts.append(self._render_summary(structured))
        parts.append(self._render_risk_level(structured))
        parts.append("---")
        parts.append(self._render_comments(structured.get("comments", [])))

        return "\n\n".join(part for part in parts if part)

    # ---------- sections ----------

    def _render_header(self) -> str:
        return "## 🤖 AI Code Review"

    def _render_summary(self, structured: Dict[str, Any]) -> str:
        summary = structured.get("summary")
        if not summary:
            return ""

        return f"### 📌 Summary\n{summary}"

    def _render_risk_level(self, structured: Dict[str, Any]) -> str:
        risk = structured.get("risk_level")
        if not risk:
            return ""

        label = RISK_LEVEL_META.get(risk, risk)
        return f"### ⚠️ Risk Level\n**{label}**"

    # ---------- comments ----------

    def _render_comments(self, comments: List[Dict[str, Any]]) -> str:
        if not comments:
            return "✅ No issues found."

        grouped = self._group_comments(comments)

        blocks: List[str] = ["## 🔍 Review Findings"]

        for severity in ("error", "warning", "info"):
            if severity not in grouped:
                continue

            meta = SEVERITY_META.get(severity, {})
            blocks.append(f"### {meta.get('icon', '')} {meta.get('label', severity)}")

            for idx, comment in enumerate(grouped[severity], start=1):
                blocks.append(self._render_single_comment(idx, comment))

        return "\n\n".join(blocks)

    def _group_comments(
        self, comments: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for c in comments:
            grouped[c.get("severity", "info")].append(c)
        return grouped

    def _render_single_comment(self, idx: int, c: Dict[str, Any]) -> str:
        severity = c.get("severity", "info")
        type_ = c.get("type")
        title = c.get("title") or "Issue"
        body = c.get("body", "")
        suggestion = c.get("suggestion")

        file_path = c.get("file_path")
        line_start = c.get("line_start")
        line_end = c.get("line_end")

        location = self._format_location(file_path, line_start, line_end)
        type_label = TYPE_META.get(type_, type_)

        parts: List[str] = []

        parts.append(f"**{idx}. {title}**")
        parts.append(f"*{type_label}* {location}".strip())

        parts.append(body)

        if suggestion:
            parts.append("#### ✅ Recommendation")
            parts.append(self._render_code_block(suggestion))

        return "\n\n".join(parts)

    # ---------- helpers ----------

    def _format_location(self, file_path, line_start, line_end) -> str:
        if not file_path:
            return ""

        if line_start and line_end:
            return f"📍 `{file_path}:{line_start}–{line_end}`"
        if line_start:
            return f"📍 `{file_path}:{line_start}`"

        return f"📍 `{file_path}`"

    def _render_code_block(self, text: str) -> str:
        text = text.strip()
        if "\n" in text or text.startswith("if ") or text.startswith("for "):
            return f"```python\n{text}\n```"
        return f"`{text}`"
