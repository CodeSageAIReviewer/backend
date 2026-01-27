import logging
from dataclasses import dataclass

from code_hosts.git_providers.factory import get_git_provider
from code_hosts.models.merge_request import MergeRequest
from reviews.exceptions import ReviewDiffError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DiffResult:
    diff_text: str
    provider: str
    repository_full_path: str
    mr_iid: str


class DiffService:
    """
    Сервис получения diff для MR/PR.

    Важно:
    - Это НЕ celery task.
    - Это чистая бизнес-логика.
    """

    def get_merge_request_diff(self, mr: MergeRequest) -> DiffResult:
        repository = mr.repository
        integration = repository.integration
        provider = get_git_provider(integration)

        # Для GitHub "iid" (PR number) — ключевой идентификатор.
        # Для GitLab чаще тоже удобно iid. external_id оставляем на будущее.
        mr_ref = mr.iid or mr.external_id

        if not mr_ref:
            raise ReviewDiffError(f"MR {mr.pk} has neither iid nor external_id")

        try:
            diff_text = provider.get_diff(repository.full_path, mr_ref)
        except Exception as exc:
            logger.exception(
                "Failed to fetch diff for MR",
                extra={
                    "mr_id": mr.pk,
                    "repo_full_path": repository.full_path,
                    "provider": integration.provider,
                    "mr_ref": mr_ref,
                },
            )
            raise ReviewDiffError(str(exc)) from exc

        return DiffResult(
            diff_text=diff_text,
            provider=integration.provider,
            repository_full_path=repository.full_path,
            mr_iid=str(mr.iid),
        )
