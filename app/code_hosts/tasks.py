import logging
from datetime import datetime

from celery import shared_task
from code_hosts.git_providers.factory import get_git_provider
from code_hosts.models.merge_request import MergeRequest, MergeRequestState
from code_hosts.models.repository import Repository
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)


def _parse_iso_datetime(value: str) -> datetime:
    dt = parse_datetime(value)
    if dt is None:
        raise ValueError(f"Failed to parse ISO datetime: {value!r}")
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.utc)
    return dt


def _build_merge_request_defaults(mr_info) -> dict:
    return {
        "iid": mr_info.iid,
        "title": mr_info.title,
        "description": mr_info.description or "",
        "author_name": mr_info.author_name,
        "author_username": mr_info.author_username or "",
        "source_branch": mr_info.source_branch,
        "target_branch": mr_info.target_branch,
        "state": mr_info.state,
        "web_url": mr_info.web_url,
        "created_at": _parse_iso_datetime(mr_info.created_at),
        "updated_at": _parse_iso_datetime(mr_info.updated_at),
    }


def _sync_repository_merge_requests(provider, repository) -> None:
    seen_external_ids: set[str] = set()
    ordered_states = [
        MergeRequestState.MERGED,
        MergeRequestState.CLOSED,
        MergeRequestState.OPEN,
    ]

    with transaction.atomic():
        for state_choice in ordered_states:
            mr_infos = provider.list_merge_requests(
                repository.full_path, state_choice.value
            )
            for mr_info in mr_infos:
                if mr_info.external_id in seen_external_ids:
                    continue
                seen_external_ids.add(mr_info.external_id)

                defaults = _build_merge_request_defaults(mr_info)
                MergeRequest.objects.update_or_create(
                    repository=repository,
                    external_id=mr_info.external_id,
                    defaults=defaults,
                )

    repository.last_synced_at = timezone.now()
    repository.save(update_fields=["last_synced_at"])


@shared_task
def sync_merge_requests(repository_id: int) -> None:
    try:
        repository = Repository.objects.select_related("integration").get(
            pk=repository_id
        )
    except Repository.DoesNotExist:
        logger.warning("Repository %s does not exist", repository_id)
        return

    provider = get_git_provider(repository.integration)

    try:
        _sync_repository_merge_requests(provider, repository)
    except Exception:
        logger.exception(
            "Failed to sync merge requests for repository %s",
            repository.full_path,
            extra={"repo_id": repository.pk},
        )
