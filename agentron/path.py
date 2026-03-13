from pathlib import Path


def get_data_dir() -> Path:
    data_dir = Path.home() / '.agentron'
    return data_dir


def get_cache_dir() -> Path:
    return get_data_dir() / 'cache'


def get_auth_table_path() -> Path:
    return get_data_dir() / 'auth.json'
