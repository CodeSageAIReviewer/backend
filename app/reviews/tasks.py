import logging

from celery import shared_task
from code_hosts.models.merge_request import MergeRequest
from django.db import transaction
from django.utils import timezone
from llm.models import LLMIntegration
from reviews.models import ReviewComment, ReviewRun, ReviewStatus
from reviews.parsers.review_output_parser import ReviewOutputParser
from reviews.services.diff_service import DiffService
from reviews.services.llm_review_service import LLMReviewService
from reviews.services.publish_service import PublishService

logger = logging.getLogger(__name__)


def _ensure_review_run(
    *,
    mr: MergeRequest,
    llm_integration: LLMIntegration,
    requested_by_id: int | None,
    review_run_id: int | None,
) -> ReviewRun | None:
    """
    Возвращает существующий ReviewRun (если передан review_run_id) или создаёт новый.
    Делает базовую валидацию соответствия MR и LLM.
    """
    if review_run_id is not None:
        try:
            review_run = ReviewRun.objects.select_related(
                "merge_request", "llm_integration"
            ).get(pk=review_run_id)
        except ReviewRun.DoesNotExist:
            logger.warning("ReviewRun %s does not exist", review_run_id)
            return None

        if (
            review_run.merge_request_id != mr.pk
            or review_run.llm_integration_id != llm_integration.pk
        ):
            logger.warning(
                "ReviewRun %s does not match MR %s or LLM integration %s",
                review_run_id,
                mr.pk,
                llm_integration.pk,
            )
            return None

        return review_run

    # Создаём новый ReviewRun
    return ReviewRun.objects.create(
        merge_request=mr,
        requested_by_id=requested_by_id,
        llm_integration=llm_integration,
        status=ReviewStatus.QUEUED,
        input_payload={
            "mr_id": mr.pk,
            "repo_full_path": mr.repository.full_path,
            "mr_iid": mr.iid,
            "source_branch": mr.source_branch,
            "target_branch": mr.target_branch,
        },
        model_name=getattr(llm_integration, "model", "")
        or getattr(llm_integration, "default_model", "")
        or "",
    )


def _upsert_review_comments(review_run: ReviewRun, drafts) -> int:
    """
    Пересоздаём комментарии ревью по данным парсера.
    На MVP — удаляем старые и создаём заново (проще и надёжнее).
    """
    # Если ты хочешь хранить историю комментариев по run — оставь как есть.
    # Если нужно мерджить — потом добавим сравнение/апдейт.
    ReviewComment.objects.filter(review_run=review_run).delete()

    objs = [
        ReviewComment(
            review_run=review_run,
            severity=d.severity,
            comment_type=d.comment_type,
            title=d.title,
            body=d.body,
            file_path=d.file_path,
            line_start=d.line_start,
            line_end=d.line_end,
            suggestion=d.suggestion,
        )
        for d in drafts
    ]
    if not objs:
        return 0

    ReviewComment.objects.bulk_create(objs, batch_size=500)
    return len(objs)


@shared_task(bind=True, autoretry_for=(), retry_backoff=False)
def run_mr_review(
    self,
    merge_request_id: int,
    llm_integration_id: int,
    requested_by_id: int | None = None,
    review_run_id: int | None = None,
    publish: bool = True,
) -> int | None:
    """
    Полный пайплайн ревью:
    - получить diff
    - вызвать LLM
    - распарсить output
    - сохранить ReviewRun + ReviewComment
    - (опционально) опубликовать в MR/PR
    """

    try:
        mr = MergeRequest.objects.select_related(
            "repository", "repository__integration"
        ).get(pk=merge_request_id)
    except MergeRequest.DoesNotExist:
        logger.warning("MergeRequest %s does not exist", merge_request_id)
        return None

    try:
        llm_integration = LLMIntegration.objects.get(pk=llm_integration_id)
    except LLMIntegration.DoesNotExist:
        logger.warning("LLMIntegration %s does not exist", llm_integration_id)
        return None

    with transaction.atomic():
        review_run = _ensure_review_run(
            mr=mr,
            llm_integration=llm_integration,
            requested_by_id=requested_by_id,
            review_run_id=review_run_id,
        )
        if review_run is None:
            return None

        # гарантируем, что payload/model_name заполнены
        if not review_run.input_payload:
            review_run.input_payload = {
                "mr_id": mr.pk,
                "repo_full_path": mr.repository.full_path,
                "mr_iid": mr.iid,
                "source_branch": mr.source_branch,
                "target_branch": mr.target_branch,
            }
        if not review_run.model_name:
            review_run.model_name = (
                getattr(llm_integration, "model", "")
                or getattr(llm_integration, "default_model", "")
                or ""
            )

        # статус RUNNING
        review_run.status = ReviewStatus.RUNNING
        review_run.started_at = timezone.now()
        review_run.error_message = ""
        review_run.save(
            update_fields=[
                "status",
                "started_at",
                "input_payload",
                "model_name",
                "error_message",
            ]
        )

    try:
        # 1) Diff
        diff_service = DiffService()
        diff_result = diff_service.get_merge_request_diff(mr)
        diff_text = diff_result.diff_text

        # 2) LLM call
        llm_service = LLMReviewService()
        llm_result = llm_service.run_review(
            mr=mr,
            llm_integration=llm_integration,
            diff_text=diff_text,
            language="ru",
        )

        # 3) Parse output -> drafts
        parser = ReviewOutputParser()
        parsed = parser.parse(
            raw_output=llm_result.raw_output,
            structured_output=llm_result.structured_output,
        )

        # 4) Persist ReviewRun + comments
        with transaction.atomic():
            review_run.raw_output = llm_result.raw_output
            review_run.structured_output = parsed.raw_structured
            saved_comments = _upsert_review_comments(review_run, parsed.comments)

            review_run.status = ReviewStatus.SUCCEEDED
            review_run.finished_at = timezone.now()
            review_run.save(
                update_fields=[
                    "raw_output",
                    "structured_output",
                    "status",
                    "finished_at",
                ]
            )

        # 5) Publish (optional)
        if publish:
            try:
                PublishService().publish_review_run(review_run)
            except Exception:
                # Публикация не должна ломать уже успешное ревью — логируем и идём дальше
                logger.exception(
                    "Publish failed for review_run=%s (mr=%s)",
                    review_run.pk,
                    mr.pk,
                    extra={"review_run_id": review_run.pk, "mr_id": mr.pk},
                )

        logger.info(
            "Review succeeded: review_run=%s, comments=%s",
            review_run.pk,
            saved_comments,
            extra={"review_run_id": review_run.pk, "mr_id": mr.pk},
        )
        return review_run.pk

    except Exception as exc:
        logger.exception(
            "Failed to run review for MR %s with LLM integration %s",
            merge_request_id,
            llm_integration_id,
            extra={
                "mr_id": merge_request_id,
                "llm_integration_id": llm_integration_id,
                "review_run_id": getattr(review_run, "pk", None),
            },
        )

        # если review_run успели создать — помечаем FAILED
        if review_run and getattr(review_run, "pk", None):
            review_run.status = ReviewStatus.FAILED
            review_run.error_message = str(exc)
            review_run.finished_at = timezone.now()
            review_run.save(update_fields=["status", "error_message", "finished_at"])
            return review_run.pk

        return None
