from code_hosts.git_providers.base import BaseGitProvider
from code_hosts.git_providers.github import GitHubProvider
from code_hosts.git_providers.gitlab import GitLabProvider
from code_hosts.models.integration import CodeHostProvider


def get_git_provider(integration) -> BaseGitProvider:
    """
    Фабрика, которая возвращает нужного провайдера
    на основе типа интеграции.
    """

    provider = integration.provider

    if provider == CodeHostProvider.GITLAB:
        return GitLabProvider(integration)

    if provider == CodeHostProvider.GITHUB:
        return GitHubProvider(integration)

    raise NotImplementedError(f"Unknown provider: {provider}")
