from agentron.model.models_dev import ModelsDevRepo
from agentron.model.openai_codex import OpenAICodexModelRepo
from agentron.model.openrouter import OpenRouterRepo
from agentron.types.model import Model
from agentron.types.repo import ModelRepo, ModelRepoPriority

_repos: list[ModelRepo] = []


def get_repos(provider: str) -> list[tuple[ModelRepoPriority, ModelRepo]]:
    global _repos
    if not _repos:
        models_dev_repo = ModelsDevRepo()
        _repos = [
            models_dev_repo,
            OpenRouterRepo(),
            OpenAICodexModelRepo(parent=models_dev_repo),
        ]

    repos = [(repo.get_priority(provider), repo) for repo in _repos]
    # Sort by priority, highest first
    repos.sort(key=lambda x: x[0], reverse=True)
    return repos


def get_model(model: str, provider: str | None = None) -> Model:
    """
    Gets a model from an internal set of auto-updated repositories.

    You can either specify a fully-qualified mode name:
        get_model('anthropic:claude-opus-4-6')
    Or equivalently:
        get_model(model='claude-opus-4-6', provider='anthropic')
    """
    if provider is None:
        if ':' in model:
            provider, model = model.split(':', 1)
        else:
            raise ValueError('Provider must be specified if the model name is not fully qualified.')

    for priority, repo in get_repos(provider):
        try:
            return repo.get_model(provider=provider, model=model)
        except LookupError:
            if priority == ModelRepoPriority.EXCLUSIVE:
                break
            else:
                continue

    raise LookupError(f'Model "{model}" from provider "{provider}" not found.')
