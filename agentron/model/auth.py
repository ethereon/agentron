import os
import json
import logging

from agentron.model.types import Model
from agentron.path import get_auth_table_path

logger = logging.getLogger(__name__)


def resolve_api_key(model: Model) -> str | None:
    # Check model-specific environment variables
    # e.g.: OPENROUTER_API_KEY
    candidates = model.get('auth_env_vars', [])
    # If no known env vars exist, auto-add a reasonable default based on the provider name
    if not candidates:
        candidates.append(f'{model["provider"].upper()}_API_KEY')
    for env_var_name in candidates:
        value = os.getenv(env_var_name)
        if value:
            return value

    # Check ~/.agentron/auth.json
    auth_table = maybe_load_api_key_table()
    if auth_table is None:
        return None
    model_specific = auth_table.get(f'{model["provider"]}/{model["id"]}')
    # Fine-grained <provider/model> keys take precedence over provider-level keys
    # e.g.: zai-coding-plan/glm-4.7
    if model_specific:
        return model_specific
    # Provider-level
    # e.g.: zai-coding-plan
    provider_specific = auth_table.get(model['provider'])
    if provider_specific:
        return provider_specific
    return None


def maybe_load_api_key_table() -> dict[str, str] | None:
    path = get_auth_table_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        logger.error('Failed to decode JSON from auth table')
        return None
