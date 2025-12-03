from code_hosts.git_providers.base import BaseGitProvider


class GitLabProvider(BaseGitProvider):
    """Реализация провайдера для GitLab."""

    def list_repositories(self):
        raise NotImplementedError

    def list_commits(self, repo_external_id, branch=None):
        raise NotImplementedError

    def list_merge_requests(self, repo_external_id):
        raise NotImplementedError

    def get_diff(self, repo_external_id, mr_external_id):
        raise NotImplementedError

    def post_comment(self, repo_external_id, mr_external_id, body):
        raise NotImplementedError

    def setup_webhook(self, repo_external_id, webhook_url):
        raise NotImplementedError

    def validate_credentials(self) -> bool:
        raise NotImplementedError
