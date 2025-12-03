"""Registry helpers for the llm app."""

LLM_REGISTRY = {}


def register(name, provider):
    LLM_REGISTRY[name] = provider


def get_provider(name):
    return LLM_REGISTRY.get(name)
