import os
import json
import logging

from functools import cache
from typing import Iterable

from agentron.path import get_auth_table_path

logger = logging.getLogger(__name__)


@cache
def get_auth_table() -> dict[str, str]:
    """
    Same as load_auth_table, but cached to avoid repeated file reads.
    """
    return load_auth_table()


def load_auth_table() -> dict[str, str]:
    """
    Load the auth table from ~/.agentron/auth.json
    """
    path = get_auth_table_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        logger.error('Failed to decode JSON from auth table')
        return {}


def resolve_auth_value(
    *,
    env_var_names: Iterable[str] = (),
    table_keys: Iterable[str] = (),
) -> str | None:
    """
    Resolve an auth value from environment variables or the auth table.
    """
    # Check env vars first
    for env_var_name in env_var_names:
        value = os.getenv(env_var_name)
        if value:
            return value

    # Check ~/.agentron/auth.json
    key_table = get_auth_table()
    for table_key in table_keys:
        value = key_table.get(table_key)
        if value:
            return value

    return None
