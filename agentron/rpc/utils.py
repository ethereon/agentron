import os
import sys
import time
import uuid
import tempfile


def get_safe_socket_path(name: str) -> str:
    """
    Generate a unique, safe Unix domain socket path that works across platforms.

    Uniqueness is guaranteed by embedding a timestamp + random UUID fragment,
    so multiple calls with the same name never collide.

    Unix domain socket path length limits (including null terminator):
      - Linux:  108 bytes
      - macOS:  104 bytes (the binding constraint)
      - Others: 104 bytes to be safe

    Strategy:
      - macOS: /tmp/<name>.sock
      - Linux: XDG_RUNTIME_DIR if available, else /tmp
      - Other Unix: tempfile.gettempdir()
      - Windows: raises NotImplementedError

    Args:
        name: A logical name for the socket (e.g. "myapp", "server").
              Will be sanitized and truncated to keep the full path safe.

    Returns:
        An absolute path string safe to use as a Unix domain socket.

    Raises:
        NotImplementedError: On Windows.
        ValueError: If a safe path cannot be constructed.
    """
    if sys.platform == 'win32':
        raise NotImplementedError('Unix domain sockets are not reliably supported on Windows. Consider using named pipes or TCP loopback instead.')

    # Sanitize name: keep only alphanumeric, hyphen, underscore
    safe_name = ''.join(c if c.isalnum() or c in '-_' else '_' for c in name)
    if not safe_name:
        safe_name = 'socket'

    # Unique suffix: 8-char hex timestamp + 6-char random UUID fragment
    # e.g. "a3f1bc92_d4e1f0" — 15 chars total including separator
    ts_hex = format(int(time.time() * 1000) & 0xFFFFFFFF, '08x')
    rand_frag = uuid.uuid4().hex[:6]
    unique_tag = f'{ts_hex}_{rand_frag}'  # e.g. "a3f1bc92_d4e1f0"

    # macOS has the tightest limit: 104 bytes total (103 usable)
    MAX_BYTES = 103

    if sys.platform == 'darwin':
        base_dir = '/tmp'
    else:
        xdg = os.environ.get('XDG_RUNTIME_DIR')
        if xdg and os.path.isdir(xdg) and os.access(xdg, os.W_OK):
            base_dir = xdg
        else:
            base_dir = tempfile.gettempdir()

    suffix = f'_{unique_tag}.sock'
    candidate = os.path.join(base_dir, safe_name + suffix)

    if len(candidate.encode()) <= MAX_BYTES:
        return candidate

    # Name too long: truncate it, keeping the full unique tag intact
    overhead = len(os.path.join(base_dir, '').encode()) + len(suffix.encode())
    max_name_bytes = MAX_BYTES - overhead
    if max_name_bytes <= 0:
        raise ValueError(f'Base directory {base_dir!r} is too long to fit a socket path within {MAX_BYTES} bytes.')

    truncated_name = safe_name.encode()[:max_name_bytes].decode(errors='ignore')
    candidate = os.path.join(base_dir, truncated_name + suffix)

    final_len = len(candidate.encode())
    if final_len > MAX_BYTES:
        raise ValueError(f'Cannot construct a socket path within {MAX_BYTES} bytes. Got {final_len} bytes: {candidate!r}')

    return candidate
