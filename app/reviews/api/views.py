import logging

from code_hosts.api.utils import format_datetime
from code_hosts.models.merge_request import MergeRequest
from code_hosts.models.workspace import Workspace, WorkspaceMembership, WorkspaceRole
from django.db.models import Count
from django.utils import timezone
from llm.models import LLMIntegration
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from reviews.models import (
    CommentSeverity,
    CommentType,
    ReviewComment,
    ReviewRun,
    ReviewStatus,
)
from reviews.services.publish_service import PublishService
from reviews.tasks import run_mr_review


class WorkspaceReviewBaseView(APIView):
    permission_classes = (IsAuthenticated,)

    def _get_workspace_and_membership(self, workspace_id):
        try:
            workspace = Workspace.objects.get(id=workspace_id)
        except Workspace.DoesNotExist:
            return None, None

        membership = WorkspaceMembership.objects.filter(
            workspace=workspace, user=self.request.user
        ).first()
        return workspace, membership

    def _has_access(self, workspace, membership) -> bool:
        if workspace is None:
            return False

        if workspace.owner_id == self.request.user.id:
            return True

        return membership is not None and membership.role in {
            WorkspaceRole.ADMIN,
            WorkspaceRole.MEMBER,
            WorkspaceRole.VIEWER,
        }

    def _has_modify_access(self, workspace, membership) -> bool:
        if workspace is None:
            return False

        if workspace.owner_id == self.request.user.id:
            return True

        return membership is not None and membership.role in {
            WorkspaceRole.ADMIN,
            WorkspaceRole.MEMBER,
        }

    def _get_merge_request(self, workspace, mr_id):
        try:
            return MergeRequest.objects.select_related(
                "repository", "repository__integration"
            ).get(id=mr_id, repository__integration__workspace=workspace)
        except MergeRequest.DoesNotExist:
            return None


def _serialize_user(user):
    if user is None:
        return None
    return {"id": user.id, "username": user.username}


def _serialize_integration(integration):
    return {
        "id": integration.id,
        "name": integration.name,
        "provider": integration.provider,
        "model": integration.model,
        "base_url": integration.base_url,
    }


def _parse_optional_bool(value, *, default=True):
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value in (0, 1):
            return bool(value)
        raise ValueError("Invalid boolean value.")
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off"}:
            return False
    raise ValueError("Invalid boolean value.")


class ReviewRunCreateView(WorkspaceReviewBaseView):
    def post(self, request, workspace_id, mr_id, *args, **kwargs):
        workspace, membership = self._get_workspace_and_membership(workspace_id)
        if workspace is None:
            return Response(
                {"detail": "Workspace not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if not self._has_modify_access(workspace, membership):
            return Response(
                {"detail": "You do not have access to this workspace."},
                status=status.HTTP_403_FORBIDDEN,
            )

        merge_request = self._get_merge_request(workspace, mr_id)
        if merge_request is None:
            return Response(
                {"detail": "Merge request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        llm_integration_id = request.data.get("llm_integration_id")
        if llm_integration_id is None:
            return Response(
                {"detail": "llm_integration_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(llm_integration_id, int):
            try:
                llm_integration_id = int(llm_integration_id)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "llm_integration_id must be an integer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            llm_integration = LLMIntegration.objects.get(
                id=llm_integration_id, owner=request.user
            )
        except LLMIntegration.DoesNotExist:
            return Response(
                {"detail": "LLM integration not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        review_run = ReviewRun.objects.create(
            merge_request=merge_request,
            requested_by=request.user,
            llm_integration=llm_integration,
            status=ReviewStatus.QUEUED,
            input_payload={
                "mr_id": merge_request.pk,
                "repo_full_path": merge_request.repository.full_path,
                "mr_iid": merge_request.iid,
                "source_branch": merge_request.source_branch,
                "target_branch": merge_request.target_branch,
            },
            model_name=llm_integration.model or "",
        )

        try:
            publish = _parse_optional_bool(request.data.get("publish"), default=True)
        except ValueError:
            return Response(
                {"detail": "publish must be a boolean."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        run_mr_review.delay(
            merge_request.id,
            llm_integration.id,
            request.user.id,
            review_run_id=review_run.id,
            publish=publish,
        )

        return Response(
            {
                "id": review_run.id,
                "merge_request_id": merge_request.id,
                "status": review_run.status,
                "requested_by": _serialize_user(review_run.requested_by),
                "llm_integration": _serialize_integration(llm_integration),
                "queued_at": format_datetime(review_run.queued_at),
            },
            status=status.HTTP_201_CREATED,
        )


class ReviewRunListView(WorkspaceReviewBaseView):
    def get(self, request, workspace_id, mr_id, *args, **kwargs):
        workspace, membership = self._get_workspace_and_membership(workspace_id)
        if workspace is None:
            return Response(
                {"detail": "Workspace not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if not self._has_access(workspace, membership):
            return Response(
                {"detail": "You do not have access to this workspace."},
                status=status.HTTP_403_FORBIDDEN,
            )

        merge_request = self._get_merge_request(workspace, mr_id)
        if merge_request is None:
            return Response(
                {"detail": "Merge request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        review_runs = (
            ReviewRun.objects.filter(merge_request=merge_request)
            .select_related("requested_by", "llm_integration")
            .annotate(comment_count=Count("comments"))
            .order_by("-queued_at")
        )

        payload = []
        for review_run in review_runs:
            raw_preview = ""
            if review_run.raw_output:
                raw_preview = review_run.raw_output[:200]

            payload.append(
                {
                    "id": review_run.id,
                    "status": review_run.status,
                    "requested_by": _serialize_user(review_run.requested_by),
                    "llm_integration": _serialize_integration(
                        review_run.llm_integration
                    ),
                    "queued_at": format_datetime(review_run.queued_at),
                    "started_at": (
                        format_datetime(review_run.started_at)
                        if review_run.started_at
                        else None
                    ),
                    "finished_at": (
                        format_datetime(review_run.finished_at)
                        if review_run.finished_at
                        else None
                    ),
                    "comment_count": review_run.comment_count,
                    "has_error": bool(review_run.error_message),
                    "output_preview": raw_preview,
                }
            )

        return Response(payload)


class ReviewRunDetailView(WorkspaceReviewBaseView):
    def get(self, request, workspace_id, mr_id, review_run_id, *args, **kwargs):
        workspace, membership = self._get_workspace_and_membership(workspace_id)
        if workspace is None:
            return Response(
                {"detail": "Workspace not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if not self._has_access(workspace, membership):
            return Response(
                {"detail": "You do not have access to this workspace."},
                status=status.HTTP_403_FORBIDDEN,
            )

        merge_request = self._get_merge_request(workspace, mr_id)
        if merge_request is None:
            return Response(
                {"detail": "Merge request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            review_run = ReviewRun.objects.select_related(
                "requested_by", "llm_integration"
            ).get(id=review_run_id, merge_request=merge_request)
        except ReviewRun.DoesNotExist:
            return Response(
                {"detail": "Review run not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        comments = ReviewComment.objects.filter(review_run=review_run).order_by("id")
        comment_payload = []
        for comment in comments:
            comment_payload.append(
                {
                    "id": comment.id,
                    "severity": comment.severity,
                    "comment_type": comment.comment_type,
                    "title": comment.title,
                    "body": comment.body,
                    "file_path": comment.file_path,
                    "line_start": comment.line_start,
                    "line_end": comment.line_end,
                    "suggestion": comment.suggestion,
                    "posted_to_vcs": comment.posted_to_vcs,
                    "posted_at": (
                        format_datetime(comment.posted_at)
                        if comment.posted_at
                        else None
                    ),
                }
            )

        return Response(
            {
                "id": review_run.id,
                "status": review_run.status,
                "requested_by": _serialize_user(review_run.requested_by),
                "llm_integration": _serialize_integration(review_run.llm_integration),
                "queued_at": format_datetime(review_run.queued_at),
                "started_at": (
                    format_datetime(review_run.started_at)
                    if review_run.started_at
                    else None
                ),
                "finished_at": (
                    format_datetime(review_run.finished_at)
                    if review_run.finished_at
                    else None
                ),
                "input_payload": review_run.input_payload,
                "raw_output": review_run.raw_output,
                "structured_output": review_run.structured_output,
                "error_message": review_run.error_message or "",
                "comments": comment_payload,
            }
        )


class ReviewRunCommentsView(WorkspaceReviewBaseView):
    def get(self, request, workspace_id, mr_id, review_run_id, *args, **kwargs):
        workspace, membership = self._get_workspace_and_membership(workspace_id)
        if workspace is None:
            return Response(
                {"detail": "Workspace not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if not self._has_access(workspace, membership):
            return Response(
                {"detail": "You do not have access to this workspace."},
                status=status.HTTP_403_FORBIDDEN,
            )

        merge_request = self._get_merge_request(workspace, mr_id)
        if merge_request is None:
            return Response(
                {"detail": "Merge request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            review_run = ReviewRun.objects.get(
                id=review_run_id, merge_request=merge_request
            )
        except ReviewRun.DoesNotExist:
            return Response(
                {"detail": "Review run not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        severity = request.query_params.get("severity")
        if severity and severity not in CommentSeverity.values:
            return Response(
                {"detail": "Invalid severity."}, status=status.HTTP_400_BAD_REQUEST
            )

        comment_type = request.query_params.get("comment_type")
        if comment_type and comment_type not in CommentType.values:
            return Response(
                {"detail": "Invalid comment_type."}, status=status.HTTP_400_BAD_REQUEST
            )

        file_path = request.query_params.get("file")
        if not file_path:
            file_path = request.query_params.get("file_path")
        if file_path is not None and not isinstance(file_path, str):
            return Response(
                {"detail": "Invalid file filter."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        comments = ReviewComment.objects.filter(review_run=review_run)
        if severity:
            comments = comments.filter(severity=severity)
        if comment_type:
            comments = comments.filter(comment_type=comment_type)
        if file_path:
            comments = comments.filter(file_path=file_path)

        comments = comments.order_by("id")

        payload = []
        for comment in comments:
            payload.append(
                {
                    "id": comment.id,
                    "severity": comment.severity,
                    "comment_type": comment.comment_type,
                    "title": comment.title,
                    "body": comment.body,
                    "file_path": comment.file_path,
                    "line_start": comment.line_start,
                    "line_end": comment.line_end,
                    "suggestion": comment.suggestion,
                    "posted_to_vcs": comment.posted_to_vcs,
                    "posted_at": (
                        format_datetime(comment.posted_at)
                        if comment.posted_at
                        else None
                    ),
                }
            )

        return Response(payload)


class ReviewRunRerunView(WorkspaceReviewBaseView):
    def post(self, request, workspace_id, mr_id, review_run_id, *args, **kwargs):
        workspace, membership = self._get_workspace_and_membership(workspace_id)
        if workspace is None:
            return Response(
                {"detail": "Workspace not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if not self._has_modify_access(workspace, membership):
            return Response(
                {"detail": "You do not have access to this workspace."},
                status=status.HTTP_403_FORBIDDEN,
            )

        merge_request = self._get_merge_request(workspace, mr_id)
        if merge_request is None:
            return Response(
                {"detail": "Merge request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            review_run = ReviewRun.objects.select_related("llm_integration").get(
                id=review_run_id, merge_request=merge_request
            )
        except ReviewRun.DoesNotExist:
            return Response(
                {"detail": "Review run not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        llm_integration = review_run.llm_integration
        llm_integration_id = request.data.get("llm_integration_id")
        if llm_integration_id is not None:
            if not isinstance(llm_integration_id, int):
                try:
                    llm_integration_id = int(llm_integration_id)
                except (TypeError, ValueError):
                    return Response(
                        {"detail": "llm_integration_id must be an integer."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            try:
                llm_integration = LLMIntegration.objects.get(
                    id=llm_integration_id, owner=request.user
                )
            except LLMIntegration.DoesNotExist:
                return Response(
                    {"detail": "LLM integration not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        try:
            publish = _parse_optional_bool(request.data.get("publish"), default=True)
        except ValueError:
            return Response(
                {"detail": "publish must be a boolean."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        input_payload = review_run.input_payload or {
            "mr_id": merge_request.pk,
            "repo_full_path": merge_request.repository.full_path,
            "mr_iid": merge_request.iid,
            "source_branch": merge_request.source_branch,
            "target_branch": merge_request.target_branch,
        }

        new_review_run = ReviewRun.objects.create(
            merge_request=merge_request,
            requested_by=request.user,
            llm_integration=llm_integration,
            status=ReviewStatus.QUEUED,
            input_payload=input_payload,
            model_name=llm_integration.model or "",
            temperature=review_run.temperature,
            max_tokens=review_run.max_tokens,
        )

        run_mr_review.delay(
            merge_request.id,
            llm_integration.id,
            request.user.id,
            review_run_id=new_review_run.id,
            publish=publish,
        )

        return Response(
            {
                "id": new_review_run.id,
                "merge_request_id": merge_request.id,
                "status": new_review_run.status,
                "requested_by": _serialize_user(new_review_run.requested_by),
                "llm_integration": _serialize_integration(llm_integration),
                "queued_at": format_datetime(new_review_run.queued_at),
                "reused_review_run_id": review_run.id,
            },
            status=status.HTTP_201_CREATED,
        )


class ReviewRunCancelView(WorkspaceReviewBaseView):
    def post(self, request, workspace_id, mr_id, review_run_id, *args, **kwargs):
        workspace, membership = self._get_workspace_and_membership(workspace_id)
        if workspace is None:
            return Response(
                {"detail": "Workspace not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if not self._has_modify_access(workspace, membership):
            return Response(
                {"detail": "You do not have access to this workspace."},
                status=status.HTTP_403_FORBIDDEN,
            )

        merge_request = self._get_merge_request(workspace, mr_id)
        if merge_request is None:
            return Response(
                {"detail": "Merge request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            review_run = ReviewRun.objects.get(
                id=review_run_id, merge_request=merge_request
            )
        except ReviewRun.DoesNotExist:
            return Response(
                {"detail": "Review run not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if review_run.status not in {ReviewStatus.QUEUED, ReviewStatus.RUNNING}:
            return Response(
                {"detail": "Only queued or running reviews can be canceled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        review_run.status = ReviewStatus.CANCELED
        review_run.finished_at = timezone.now()
        review_run.save(update_fields=["status", "finished_at"])

        return Response(
            {
                "id": review_run.id,
                "status": review_run.status,
                "finished_at": format_datetime(review_run.finished_at),
            }
        )


logger = logging.getLogger(__name__)


class ReviewRunPublishView(WorkspaceReviewBaseView):
    def post(self, request, workspace_id, mr_id, review_run_id, *args, **kwargs):
        workspace, membership = self._get_workspace_and_membership(workspace_id)
        if workspace is None:
            return Response(
                {"detail": "Workspace not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if not self._has_modify_access(workspace, membership):
            return Response(
                {"detail": "You do not have access to this workspace."},
                status=status.HTTP_403_FORBIDDEN,
            )

        merge_request = self._get_merge_request(workspace, mr_id)
        if merge_request is None:
            return Response(
                {"detail": "Merge request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            review_run = ReviewRun.objects.select_related(
                "merge_request__repository__integration"
            ).get(id=review_run_id, merge_request=merge_request)
        except ReviewRun.DoesNotExist:
            return Response(
                {"detail": "Review run not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            result = PublishService().publish_review_run(review_run)
        except NotImplementedError:
            return Response(
                {"detail": "Publishing comments is not supported by provider."},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )
        except Exception:
            logger.exception(
                "Publish failed for review_run=%s (mr=%s)",
                review_run.pk,
                merge_request.pk,
                extra={"review_run_id": review_run.pk, "mr_id": merge_request.pk},
            )
            return Response(
                {"detail": "Publish failed."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "posted": result.posted,
                "provider": result.provider,
                "repository_full_path": result.repository_full_path,
                "mr_iid": result.mr_iid,
            }
        )
