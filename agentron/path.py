import inspect

from pathlib import Path
from functools import cache


def get_module_path() -> Path:
    return Path(__file__).resolve().parent


def get_data_dir() -> Path:
    data_dir = Path.home() / '.agentron'
    return data_dir


def get_cache_dir() -> Path:
    return get_data_dir() / 'cache'


def get_auth_table_path() -> Path:
    return get_data_dir() / 'auth.json'


def maybe_get_dist_path(package_name: str) -> Path | None:
    # Production: agentron/dist/<package>
    module_root = get_module_path()
    dist_pkg_path = module_root / 'dist' / package_name
    return dist_pkg_path if dist_pkg_path.exists() else None


def get_dev_package_path(package_name: str) -> Path:
    module_root = get_module_path()
    return module_root.parent / 'packages' / package_name


@cache
def get_flux_path() -> Path:
    dist_path = maybe_get_dist_path('flux')
    return (
        # Production
        dist_path / 'agentron-flux.js'
        if dist_path is not None
        # Dev (non-bundled)
        else get_dev_package_path('flux') / 'dist' / 'main.js'
    )


@cache
def get_webui_root() -> Path:
    dist_path = maybe_get_dist_path('webui')
    return (
        # Production
        dist_path
        if dist_path is not None
        # Dev
        else get_dev_package_path('webui') / 'dist' / 'bundle'
    )


def resolve_external_caller_path() -> Path:
    module_dir = get_module_path()
    for frame_info in inspect.stack()[1:]:
        caller_path = Path(frame_info.filename).absolute()
        if not caller_path.is_relative_to(module_dir):
            return caller_path.parent

    # Fall back to the current working directory if no external caller is found.
    return Path.cwd()
