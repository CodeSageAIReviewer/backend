from typing import List

import requests

from code_hosts.git_providers.base import (
    BaseGitProvider,
    MergeRequestInfo,
    RepositoryInfo,
)


class GitHubProvider(BaseGitProvider):
    """Реализация провайдера для GitHub."""

    BASE_API_URL = "https://api.github.com"

    def _headers(self):
        return {
            "Authorization": f"token {self.integration.access_token}",
            "Accept": "application/vnd.github+json",
        }

    def list_repositories(self) -> List[RepositoryInfo]:
        """
        Подтягивает все репозитории, доступные пользователю:
        - его личные
        - репозитории организаций
        - коллаборативные
        """

        repos = []
        url = f"{self.BASE_API_URL}/user/repos?per_page=100&type=all"

        while url:
            response = requests.get(url, headers=self._headers())
            response.raise_for_status()

            data = response.json()

            for repo in data:
                repos.append(
                    RepositoryInfo(
                        external_id=str(repo["id"]),
                        name=repo["name"],
                        full_path=repo["full_name"],  # org/repo
                        default_branch=repo.get("default_branch") or "main",
                        web_url=repo.get("html_url"),
                    )
                )

            # Handle pagination via Link header
            url = self._get_next_page(response)

        return repos

    def _get_next_page(self, response) -> str | None:
        """
        GitHub uses the Link header for pagination:
        Link: <https://api.github.com/...page=2>; rel="next"
        """

        link = response.headers.get("Link")
        if not link:
            return None

        # Parse links
        parts = link.split(",")
        for part in parts:
            section = part.split(";")
            if len(section) < 2:
                continue

            url = section[0].strip()[1:-1]  # remove <>
            rel = section[1].strip()

            if rel == 'rel="next"':
                return url

        return None

    def list_commits(self, repo_external_id, branch=None):
        raise NotImplementedError

    def list_merge_requests(
        self, repo_full_path: str, state: str | None = None
    ) -> List[MergeRequestInfo]:
        """
        Возвращает Pull Requests из репозитория GitHub.
        repo_full_path — строка вида 'owner/repo'
        """

        api_state = None
        merged_only = False
        if state:
            if state == "merged":
                api_state = "closed"
                merged_only = True
            else:
                api_state = state

        url = f"{self.BASE_API_URL}/repos/{repo_full_path}/pulls?per_page=100"
        if api_state:
            url += f"&state={api_state}"

        prs = []
        while url:
            response = requests.get(url, headers=self._headers())
            response.raise_for_status()

            data = response.json()

            for pr in data:
                if merged_only and pr.get("merged_at") is None:
                    continue

                prs.append(
                    MergeRequestInfo(
                        external_id=str(pr["id"]),
                        iid=str(pr["number"]),  # локальный ID PR
                        title=pr["title"],
                        description=pr.get("body") or "",
                        author_name=pr["user"]["login"],
                        author_username=pr["user"]["login"],
                        source_branch=pr["head"]["ref"],
                        target_branch=pr["base"]["ref"],
                        state="merged" if merged_only else pr["state"],
                        web_url=pr["html_url"],
                        created_at=pr["created_at"],
                        updated_at=pr["updated_at"],
                        merged_at=pr.get("merged_at"),
                    )
                )

            # Pagination
            url = self._get_next_page(response)

        return prs

    def get_diff(self, repo_external_id, mr_external_id):
        raise NotImplementedError

    def post_comment(self, repo_external_id, mr_external_id, body):
        raise NotImplementedError

    def setup_webhook(self, repo_external_id, webhook_url):
        raise NotImplementedError

    def validate_credentials(self) -> bool:
        raise NotImplementedError
