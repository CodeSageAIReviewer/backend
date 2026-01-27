import logging
from dataclasses import dataclass
from typing import Iterable

from code_hosts.git_providers.factory import get_git_provider
from django.db import transaction
from django.utils import timezone
from reviews.models import ReviewComment, ReviewRun
from reviews.renderers.markdown_renderer import MarkdownReviewRenderer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PublishResult:
    posted: bool
    provider: str
    repository_full_path: str
    mr_iid: str


class PublishService:
    """
    Публикация комментариев ревью обратно в MR/PR.
    MVP: публикуем 1 общий комментарий.
    """

    def publish_review_run(self, review_run: ReviewRun) -> PublishResult:
        mr = review_run.merge_request
        repo = mr.repository
        integration = repo.integration

        provider = get_git_provider(integration)

        renderer = MarkdownReviewRenderer()
        structured = review_run.structured_output or {}
        body = renderer.render(structured)

        if not body.strip() and review_run.raw_output:
            body = "## 🤖 AI Code Review\n\n" + review_run.raw_output

        if not body.strip():
            logger.info("No content to publish for review_run=%s", review_run.pk)
            return PublishResult(
                posted=False,
                provider=integration.provider,
                repository_full_path=repo.full_path,
                mr_iid=str(mr.iid),
            )

        # (опционально) лимит длины
        max_len = 60_000
        if len(body) > max_len:
            body = body[:max_len] + "\n\n[TRUNCATED]\n"

        # СНАЧАЛА публикуем
        provider.post_comment(repo.full_path, str(mr.iid), body)

        # ПОТОМ отмечаем как опубликованное
        with transaction.atomic():
            ReviewComment.objects.filter(review_run=review_run).update(
                posted_to_vcs=True,
                posted_at=timezone.now(),
            )

        return PublishResult(
            posted=True,
            provider=integration.provider,
            repository_full_path=repo.full_path,
            mr_iid=str(mr.iid),
        )
