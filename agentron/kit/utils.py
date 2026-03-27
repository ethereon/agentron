from pathlib import Path


def resolve_path(path: Path | str) -> Path:
    """
    Resolves a given file path to an absolute path.
    If the path is already absolute, it is returned as is.
    If the path is relative, it is resolved against the current working directory.
    """
    resolved = Path(path).expanduser()
    return (
        resolved
        if resolved.is_absolute()
        # Technically, always resolve() should also do the right thing.
        # However, it will transform absolute paths to their canonical form,
        # (e.g.: /tmp/ -> /private/tmp/ on macOS), which may be unexpected.
        # Thus, only resolve relative paths.
        else resolved.resolve()
    )
