from unittest.mock import patch

from agentron.model.auth import resolve_api_key
from agentron.model.repo import get_model
from agentron.types.model import Model
from agentron.types.repo import ModelRepoPriority


class _FakeRepo:
    def __init__(self, result: Model) -> None:
        self.result = result
        self.calls: list[tuple[str, str]] = []

    def get_model(self, provider: str, model: str) -> Model:
        self.calls.append((provider, model))
        return self.result


def _make_model() -> Model:
    return {
        'id': 'openrouter/free',
        'name': 'OpenRouter Free',
        'api': 'openai-completions',
        'provider': 'openrouter',
        'base_url': 'https://openrouter.ai/api/v1',
        'reasoning': False,
        'input': ['text'],
        'cost': {
            'input': 0,
            'output': 0,
            'cache_read': 0,
            'cache_write': 0,
        },
        'context_window': 32000,
        'max_tokens': 4096,
    }


def test_get_model_parses_colon_delimited_spec() -> None:
    expected = _make_model()
    repo = _FakeRepo(expected)

    with patch('agentron.model.repo.get_repos', return_value=[(ModelRepoPriority.DEFAULT, repo)]):
        result = get_model('openrouter:openrouter/free')

    assert result == expected
    assert repo.calls == [('openrouter', 'openrouter/free')]


def test_resolve_api_key_prefers_colon_delimited_auth_key() -> None:
    model = _make_model()

    with (
        patch('agentron.model.auth.os.getenv', return_value=None),
        patch(
            'agentron.model.auth.maybe_load_api_key_table',
            return_value={
                'openrouter:openrouter/free': 'new-key',
                'openrouter/openrouter/free': 'old-key',
            },
        ),
    ):
        result = resolve_api_key(model)

    assert result == 'new-key'
