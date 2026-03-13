import json
import logging

from agentron.model.types import Model
from agentron.path import get_auth_table_path

logger = logging.getLogger(__name__)


def resolve_api_key(model: Model) -> str | None:
    auth_table = maybe_load_api_key_table()
    if auth_table is None:
        return None
    return auth_table.get(f'{model["provider"]}/{model["id"]}')


def maybe_load_api_key_table() -> dict[str, str] | None:
    path = get_auth_table_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        logger.error('Failed to decode JSON from auth table')
        return None
