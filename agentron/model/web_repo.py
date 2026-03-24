import json
import logging

from typing import Any, TypeGuard
from urllib.error import HTTPError, URLError
from urllib.request import urlopen, Request

from agentron.types.model import Model
from agentron.path import get_cache_dir

logger = logging.getLogger(__name__)


class MetadataFetchError(RuntimeError):
    pass


class WebModelRepo[T]:
    def __init__(self, *, url: str, cache_name: str) -> None:
        self._url = url
        self._cache_path = get_cache_dir() / cache_name
        self._manifest: T | None = None

    def get_model(self, provider: str, model: str) -> Model:
        if not self._is_supported_provider(provider):
            raise LookupError(f'Provider "{provider}" not supported by this repository.')

        if self._manifest is None:
            self._maybe_load_cached_manifest()

        # If loading from the cache succeeded, check in there first.
        if self._manifest is not None:
            match = self._find(provider, model)
            if match is not None:
                return match

        # Fetch from the server and re-try finding the model.
        self.fetch_manifest()
        match = self._find(provider, model)

        if match is None:
            raise LookupError(f'Model "{model}" from provider "{provider}" not found.')

        return match

    def _is_supported_provider(self, provider: str) -> bool:
        # May be overridden by subclasses to short-circuit unsupported providers.
        return True

    def _maybe_load_cached_manifest(self) -> bool:
        try:
            payload = self._cache_path.read_text(encoding='utf-8')
            data = json.loads(payload)
        except FileNotFoundError:
            return False
        except (OSError, json.JSONDecodeError):
            return False

        if not self.validate(data):
            logger.warning(f'Cached manifest at {self._cache_path} failed validation.')
            return False

        self._manifest = data
        return True

    def fetch_manifest(self) -> T:
        try:
            with urlopen(
                Request(
                    url=self._url,
                    # Certain providers like models.dev will reject the
                    # request (403) without a User-Agent header.
                    headers={'User-Agent': 'Agentron'},
                ),
                timeout=30,
            ) as response:
                charset = response.headers.get_content_charset('utf-8')
                payload = response.read().decode(charset)
        except (HTTPError, URLError, OSError) as exc:
            raise MetadataFetchError(f'Failed to fetch manifest from {self._url}.') from exc

        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise MetadataFetchError(f'Manifest from {self._url} contains invalid JSON.') from exc

        data = self._transform_payload(data)

        if not self.validate(data):
            raise MetadataFetchError(f'Manifest from {self._url} failed validation.')

        data = self._filter_validated(data)
        self._write_cached_manifest(data)
        self._manifest = data

        return data

    def _write_cached_manifest(self, manifest: T) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._cache_path.with_suffix(f'{self._cache_path.suffix}.tmp')
        tmp_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True),
            encoding='utf-8',
        )
        tmp_path.replace(self._cache_path)

    def _transform_payload(self, data: Any) -> Any:
        # Hook for subclasses to transform the raw fetched data before validation.
        return data

    def _filter_validated(self, data: T) -> T:
        # Hook for subclasses to transform the validated data before caching.
        return data

    def validate(self, data: dict | list) -> TypeGuard[T]:
        # Hook for optional subclass validation
        return isinstance(data, (dict, list))

    def _find(self, provider: str, model: str) -> Model | None:
        raise NotImplementedError()
