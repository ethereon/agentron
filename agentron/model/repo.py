from typing import Protocol

from agentron.model.models_dev import ModelsDevRepo
from agentron.model.openrouter import OpenRouterRepo
from agentron.model.types import Model


class ModelRepo(Protocol):
    def get_model(self, provider: str, model: str) -> Model: ...

    def get_priority(self, provider: str) -> int:
        """
        Repositories with higher priority will be searched first when looking up models.
        The default priority is 0.
        """
        ...


_repos: list[ModelRepo] = []


def get_repos(provider: str) -> list[ModelRepo]:
    global _repos
    if not _repos:
        _repos = [
            ModelsDevRepo(),
            OpenRouterRepo(),
        ]

    # Sort repos by priority for the given provider
    return sorted(
        _repos,
        key=lambda repo: repo.get_priority(provider),
        reverse=True,
    )


def get_model(model: str, provider: str | None = None) -> Model:
    """
    Gets a model from an internal set of auto-updated repositories.

    You can either specify a fully-qualified mode name:
        get_model('anthropic/claude-opus-4-6')
    Or equivalently:
        get_model(model='claude-opus-4-6', provider='anthropic')
    """
    if provider is None:
        if '/' in model:
            provider, model = model.split('/', 1)
        else:
            raise ValueError('Provider must be specified if the model name is not fully qualified.')

    for repo in get_repos(provider):
        try:
            return repo.get_model(provider=provider, model=model)
        except LookupError:
            continue

    raise LookupError(f'Model "{model}" from provider "{provider}" not found.')
