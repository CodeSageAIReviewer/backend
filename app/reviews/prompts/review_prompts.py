from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ReviewPrompt:
    system: str
    user: str


def build_review_prompt(
    *,
    repo_full_path: str,
    mr_iid: str,
    mr_title: str,
    mr_description: str,
    source_branch: str,
    target_branch: str,
    diff_text: str,
    language: str = "ru",
    max_diff_chars: int = 120_000,
) -> ReviewPrompt:
    """
    Собирает системный и пользовательский промпт для AI code review.

    Важно:
    - Ограничиваем diff по длине, чтобы не улететь в контекст/токены.
    - Формат ответа делаем структурированным (JSON), чтобы дальше парсить в ReviewComment.
    """

    if len(diff_text) > max_diff_chars:
        diff_text = diff_text[:max_diff_chars] + "\n\n[TRUNCATED]\n"

    system = (
        "You are a senior software engineer performing a strict code review.\n"
        "Focus on correctness, security, performance, readability, and maintainability.\n"
        "Be concise but actionable. If something is uncertain, say so.\n"
        "Return your answer strictly as JSON following the provided schema.\n"
    )

    schema = {
        "summary": "string - краткое резюме",
        "risk_level": "string enum: low|medium|high",
        "comments": [
            {
                "severity": "string enum: info|warning|error",
                "type": "string enum: general|code_smell|bug|security|performance|style|tests|documentation",
                "title": "string (optional)",
                "body": "string - замечание и рекомендация",
                "file_path": "string (optional)",
                "line_start": "int (optional)",
                "line_end": "int (optional)",
                "suggestion": "string (optional, patch/snippet)",
            }
        ],
    }

    user = (
        f"Context:\n"
        f"- Repository: {repo_full_path}\n"
        f"- MR/PR: !{mr_iid}\n"
        f"- Title: {mr_title}\n"
        f"- Description: {mr_description or ''}\n"
        f"- Source branch: {source_branch}\n"
        f"- Target branch: {target_branch}\n\n"
        f"Task:\n"
        f"1) Review the diff.\n"
        f"2) Provide issues and concrete improvements.\n"
        f"3) If you propose code changes, include short snippets.\n\n"
        f"Output format:\n"
        f"Return STRICT JSON matching this schema (no markdown, no extra text):\n"
        f"{schema}\n\n"
        f"DIFF:\n"
        f"{diff_text}\n"
    )

    # Можно добавить языковую настройку в user/system (оставляю минимально)
    if language.lower() == "ru":
        system = system + "You may write the content in Russian.\n"

    return ReviewPrompt(system=system, user=user)
