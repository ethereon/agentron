from typing import Iterable

from agentron.types.model import Model
from agentron.rpc.api import ApiKeySource
from agentron.auth import resolve_auth_value


def resolve_api_key(model: Model) -> ApiKeySource | None:
    return resolve_auth_value(
        env_var_names=_get_model_api_key_env_vars(model),
        table_keys=_get_model_auth_table_keys(model),
    )


def _get_model_api_key_env_vars(model: Model) -> Iterable[str]:
    # Check model-specific environment variables
    # e.g.: OPENROUTER_API_KEY
    candidates = model.get('auth_env_vars')
    if candidates:
        yield from candidates
    else:
        # No known env vars exists.
        # Try a reasonable default based on the provider name.
        yield f'{model["provider"].upper()}_API_KEY'


def _get_model_auth_table_keys(model: Model) -> Iterable[str]:
    # Fine-grained <provider:model> keys take precedence over provider-level keys
    # e.g.: zai-coding-plan:glm-4.7
    yield f'{model["provider"]}:{model["id"]}'

    # Provider-level
    # e.g.: zai-coding-plan
    yield model['provider']
