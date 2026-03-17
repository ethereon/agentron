import inspect

from pathlib import Path


def get_data_dir() -> Path:
    data_dir = Path.home() / '.agentron'
    return data_dir


def get_cache_dir() -> Path:
    return get_data_dir() / 'cache'


def get_auth_table_path() -> Path:
    return get_data_dir() / 'auth.json'


def get_js_packages_root() -> Path:
    return Path(__file__).resolve().parent.parent / 'packages'


def get_flux_root() -> Path:
    return get_js_packages_root() / 'flux' / 'dist'


def get_webui_root() -> Path:
    return get_js_packages_root() / 'webui' / 'dist'


def get_module_path() -> Path:
    return Path(__file__).resolve().parent


def resolve_external_caller_path() -> Path:
    module_dir = get_module_path()
    for frame_info in inspect.stack()[1:]:
        caller_path = Path(frame_info.filename).absolute()
        if not caller_path.is_relative_to(module_dir):
            return caller_path.parent

    # Fall back to the current working directory if no external caller is found.
    return Path.cwd()
