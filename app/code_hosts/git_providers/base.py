from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class RepositoryInfo:
    external_id: str
    name: str
    full_path: str
    default_branch: str
    web_url: Optional[str] = None


@dataclass
class CommitInfo:
    hash: str
    message: str
    author_name: str
    author_email: str
    authored_date: str  # ISO datetime string


@dataclass
class MergeRequestInfo:
    external_id: str
    iid: str
    title: str
    description: str
    author_name: str
    author_username: Optional[str]
    source_branch: str
    target_branch: str
    state: str
    web_url: Optional[str]
    created_at: str
    updated_at: str


class BaseGitProvider(ABC):
    """Абстрактный интерфейс для GitLab, GitHub и других Git-провайдеров."""

    def __init__(self, integration):
        self.integration = integration  # CodeHostIntegration

    # ----------------------------------------------------
    # 1. Репозитории
    # ----------------------------------------------------
    @abstractmethod
    def list_repositories(self) -> List[RepositoryInfo]:
        """Возвращает список всех доступных репозиториев."""

    # ----------------------------------------------------
    # 2. Коммиты
    # ----------------------------------------------------
    @abstractmethod
    def list_commits(
        self, repo_external_id: str, branch: Optional[str] = None
    ) -> List[CommitInfo]:
        """Возвращает список коммитов репозитория."""

    # ----------------------------------------------------
    # 3. Merge Requests / Pull Requests
    # ----------------------------------------------------
    @abstractmethod
    def list_merge_requests(self, repo_external_id: str) -> List[MergeRequestInfo]:
        """Возвращает список MR/PR репозитория."""

    @abstractmethod
    def get_diff(self, repo_external_id: str, mr_external_id: str) -> str:
        """Возвращает diff текста MR/PR."""

    # ----------------------------------------------------
    # 4. Комментарии в MR (для AI code review)
    # ----------------------------------------------------
    @abstractmethod
    def post_comment(
        self, repo_external_id: str, mr_external_id: str, body: str
    ) -> None:
        """Публикует комментарий в MR/PR."""

    # ----------------------------------------------------
    # 5. Webhooks (опционально)
    # ----------------------------------------------------
    @abstractmethod
    def setup_webhook(self, repo_external_id: str, webhook_url: str) -> None:
        """Создаёт webhook на стороне Git-провайдера."""

    # ----------------------------------------------------
    # 6. Health check интеграции
    # ----------------------------------------------------
    @abstractmethod
    def validate_credentials(self) -> bool:
        """Проверяет, действителен ли токен / доступ к API."""
