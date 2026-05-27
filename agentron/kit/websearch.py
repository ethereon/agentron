from __future__ import annotations

import json

from collections.abc import Callable, Iterable, Sequence
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from agentron.auth import resolve_auth_value
from agentron.tool.error import ToolError

DEFAULT_BRAVE_RESULT_FILTERS = (
    'discussions',
    'faq',
    'infobox',
    'news',
    'query',
    'summarizer',
    'web',
    # SKIP: 'locations',
    # SKIP: 'videos',
)


class BraveWebSearchError(ToolError):
    pass


type SearchResultFormatter = Callable[[dict[str, Any]], str]


class BraveWebSearch:
    """
    Search the web using the Brave Search API.
    https://brave.com/search/api/
    """

    def __init__(
        self,
        *,
        # Brave Search API key.
        # If not provided, attempts to auto-resolve from the following sources:
        # - Environment variable named BRAVE_WEB_SEARCH_API_KEY
        # - ~/.agentron/auth.json entry for "brave-web-search"
        api_key: str | None = None,
        # Country code for the search results. [default: 'US']
        country: str | None = None,
        # Language code for returned search results. [default: 'en']
        search_lang: str | None = None,
        # Preferred UI language for localized response text. [default: 'en-US']
        ui_lang: str | None = None,
        # Adult-content filtering level. [default: 'moderate']
        safesearch: str | None = None,
        # Whether Brave should spell-check the query. [default: true]
        spellcheck: bool | None = None,
        # Freshness filter token or date range. [default: '']
        freshness: str | None = None,
        # Whether snippets include highlight markers. [default: true]
        text_decorations: bool | None = None,
        # Result types to include in the response.
        # Available filters include: discussions, faq, infobox, news, query, summarizer, videos, web, locations
        # Explicitly provide None to allow all result types.
        result_filter: Sequence[str] | None = DEFAULT_BRAVE_RESULT_FILTERS,
        # Measurement system used in localized answers.
        units: str | None = None,
        # Deprecated goggle identifier.
        goggles_id: str | None = None,
        # One or more goggles used for custom reranking.
        goggles: str | Sequence[str] | None = None,
        # Whether to request additional snippets.
        extra_snippets: bool | None = None,
        # Whether to include summary-generation metadata.
        summary: bool | None = None,
        # Whether to enable rich-result callback metadata. [default: false]
        enable_rich_callback: bool | None = None,
        # Whether to include fetch metadata in results. [default: false]
        include_fetch_metadata: bool | None = None,
        # Whether to apply Brave search operators. [default: true]
        operators: bool | None = None,
        # Client latitude used for local result ranking.
        x_loc_lat: float | None = None,
        # Client longitude used for local result ranking.
        x_loc_long: float | None = None,
        # Client IANA timezone header.
        x_loc_timezone: str | None = None,
        # Client city header.
        x_loc_city: str | None = None,
        # Client state or region code header.
        x_loc_state: str | None = None,
        # Client state or region name header.
        x_loc_state_name: str | None = None,
        # Client country code header.
        x_loc_country: str | None = None,
        # Client postal code header.
        x_loc_postal_code: str | None = None,
        # Brave API version header.
        api_version: str | None = None,
        # Accept header sent to the API. [default: 'application/json']
        accept: str | None = None,
        # Cache-Control header value.
        cache_control: str | None = None,
        # User-Agent header value.
        user_agent: str | None = None,
        # Optional formatter for transforming the raw JSON response.
        formatter: SearchResultFormatter | None = None,
        # Network timeout in seconds.
        timeout: float = 30.0,
        # Search endpoint URL.
        base_url: str = 'https://api.search.brave.com/res/v1/web/search',
    ) -> None:
        self._base_url = base_url
        self._timeout = timeout
        self._formatter = formatter or format_brave_search_results
        self._query_defaults = {
            'country': country,
            'search_lang': search_lang,
            'ui_lang': ui_lang,
            'safesearch': safesearch,
            'spellcheck': spellcheck,
            'freshness': freshness,
            'text_decorations': text_decorations,
            'result_filter': list(result_filter) if result_filter is not None else None,
            'units': units,
            'goggles_id': goggles_id,
            'goggles': list(goggles) if isinstance(goggles, Sequence) and not isinstance(goggles, str) else goggles,
            'extra_snippets': extra_snippets,
            'summary': summary,
            'enable_rich_callback': enable_rich_callback,
            'include_fetch_metadata': include_fetch_metadata,
            'operators': operators,
        }
        self._headers = {
            'Accept': accept,
            'X-Subscription-Token': _resolve_brave_search_api_key(api_key),
            'X-Loc-Lat': x_loc_lat,
            'X-Loc-Long': x_loc_long,
            'X-Loc-Timezone': x_loc_timezone,
            'X-Loc-City': x_loc_city,
            'X-Loc-State': x_loc_state,
            'X-Loc-State-Name': x_loc_state_name,
            'X-Loc-Country': x_loc_country,
            'X-Loc-Postal-Code': x_loc_postal_code,
            'Api-Version': api_version,
            'Cache-Control': cache_control,
            'User-Agent': user_agent,
        }

    def __call__(self, query: str, count: int | None = None, offset: int | None = None) -> str:
        """
        Search the web with Brave Search and return LLM-friendly results.

        Args:
                query: The user's search query term.
                count: Number of web results to request. [default: 20]
                offset: Zero-based page offset for pagination. [default: 0]
        Returns:
                A formatted summary of the Brave Search response.
        """
        params = dict(self._query_defaults)
        params['q'] = query
        params['count'] = count
        params['offset'] = offset

        request = Request(
            url=f'{self._base_url}?{urlencode(_normalize_query_params(params), doseq=True)}',
            headers=_normalize_headers(self._headers),
        )

        try:
            with urlopen(request, timeout=self._timeout) as response:
                charset = response.headers.get_content_charset('utf-8')
                payload = json.loads(response.read().decode(charset))
        except HTTPError as exc:
            raise BraveWebSearchError(_format_http_error(exc)) from exc
        except (URLError, OSError, json.JSONDecodeError) as exc:
            raise BraveWebSearchError('Failed to retrieve results from Brave Search.') from exc

        return self._formatter(payload)


def format_brave_search_results(payload: dict[str, Any]) -> str:
    lines: list[str] = []

    query = payload.get('query')
    if isinstance(query, dict):
        original = query.get('original')
        altered = query.get('altered')
        if original:
            lines.append(f'Query: {original}')
        if altered and altered != original:
            lines.append(f'Altered query: {altered}')
        if query.get('country'):
            lines.append(f'Country: {query["country"]}')
        if query.get('more_results_available') is not None:
            lines.append(f'More results available: {query["more_results_available"]}')

    infobox = payload.get('infobox')
    if isinstance(infobox, dict):
        infobox_lines = _format_infobox(infobox)
        if infobox_lines:
            lines.extend(['', 'Infobox:'])
            lines.extend(infobox_lines)

    web_results = _extract_results(payload.get('web'))
    if web_results:
        lines.extend(['', 'Web results:'])
        lines.extend(_format_result_block(web_results))

    news_results = _extract_results(payload.get('news'))
    if news_results:
        lines.extend(['', 'News results:'])
        lines.extend(_format_result_block(news_results))

    video_results = _extract_results(payload.get('videos'))
    if video_results:
        lines.extend(['', 'Video results:'])
        lines.extend(_format_result_block(video_results))

    discussions_results = _extract_results(payload.get('discussions'))
    if discussions_results:
        lines.extend(['', 'Discussions:'])
        lines.extend(_format_result_block(discussions_results))

    faq_entries = _extract_results(payload.get('faq'))
    if faq_entries:
        lines.extend(['', 'FAQ:'])
        for index, entry in enumerate(faq_entries, start=1):
            title = _first_text(entry, 'question', 'title') or 'Untitled FAQ entry'
            answer = _first_text(entry, 'answer', 'description')
            lines.append(f'{index}. {title}')
            if answer:
                lines.append(f'   Answer: {answer}')

    location_results = _extract_results(payload.get('locations'))
    if location_results:
        lines.extend(['', 'Locations:'])
        lines.extend(_format_result_block(location_results))

    summarizer = payload.get('summarizer')
    if isinstance(summarizer, dict) and summarizer.get('key'):
        lines.extend(['', f'Summary key: {summarizer["key"]}'])

    rich = payload.get('rich')
    if isinstance(rich, dict) and rich:
        lines.extend(['', 'Rich results metadata:', _compact_json(rich)])

    if not lines:
        return _compact_json(payload)

    return '\n'.join(lines)


def _normalize_query_params(params: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            normalized[key] = 'true' if value else 'false'
            continue
        if key == 'result_filter' and isinstance(value, Sequence) and not isinstance(value, str):
            normalized[key] = ','.join(value)
            continue
        normalized[key] = value
    return normalized


def _normalize_headers(headers: dict[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in headers.items():
        if value is None:
            continue
        if isinstance(value, bool):
            normalized[key] = 'true' if value else 'false'
            continue
        normalized[key] = str(value)
    return normalized


def _format_http_error(error: HTTPError) -> str:
    try:
        payload = error.read().decode('utf-8')
    except OSError:
        payload = ''

    if payload:
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            parsed = payload.strip()
        else:
            details = parsed.get('error') if isinstance(parsed, dict) else None
            if isinstance(details, dict):
                message = details.get('detail') or details.get('message')
                if message:
                    return f'Brave Search request failed ({error.code}): {message}'
            return f'Brave Search request failed ({error.code}): {_compact_json(parsed)}'

    return f'Brave Search request failed ({error.code}).'


def _extract_results(section: Any) -> list[dict[str, Any]]:
    if not isinstance(section, dict):
        return []

    results = section.get('results')
    if isinstance(results, list):
        return [item for item in results if isinstance(item, dict)]

    faq_items = section.get('items')
    if isinstance(faq_items, list):
        return [item for item in faq_items if isinstance(item, dict)]

    return []


def _format_infobox(infobox: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    title = _first_text(infobox, 'title', 'label', 'name')
    description = _first_text(infobox, 'description', 'long_desc', 'snippet')
    url = _first_text(infobox, 'url')

    if title:
        lines.append(f'- Title: {title}')
    if description:
        lines.append(f'- Description: {description}')
    if url:
        lines.append(f'- URL: {url}')

    attributes = infobox.get('attributes')
    if isinstance(attributes, Iterable) and not isinstance(attributes, (str, bytes, dict)):
        for item in attributes:
            if not isinstance(item, dict):
                continue
            label = _first_text(item, 'label', 'name')
            value = _first_text(item, 'value', 'description')
            if label and value:
                lines.append(f'- {label}: {value}')

    return lines


def _format_result_block(results: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for index, result in enumerate(results, start=1):
        title = _first_text(result, 'title', 'name') or 'Untitled result'
        url = _first_text(result, 'url', 'profile', 'thumbnail')
        description = _first_text(result, 'description', 'snippet')

        lines.append(f'{index}. {title}')
        if url:
            lines.append(f'   URL: {url}')
        if description:
            lines.append(f'   Snippet: {description}')

        age = _first_text(result, 'age')
        if age:
            lines.append(f'   Age: {age}')

        language = _first_text(result, 'language')
        if language:
            lines.append(f'   Language: {language}')

        extra_snippets = result.get('extra_snippets')
        if isinstance(extra_snippets, list):
            for extra_index, snippet in enumerate(extra_snippets, start=1):
                if isinstance(snippet, str) and snippet:
                    lines.append(f'   Extra snippet {extra_index}: {snippet}')

    return lines


def _first_text(value: Any, *keys: str) -> str | None:
    if not isinstance(value, dict):
        return None

    for key in keys:
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate:
            return candidate

    return None


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(',', ':'))


def _resolve_brave_search_api_key(provided_key: str | None) -> str:
    if provided_key:
        return provided_key

    resolved = resolve_auth_value(
        env_var_names=['BRAVE_WEB_SEARCH_API_KEY'],
        table_keys=['brave-web-search'],
    )
    if resolved:
        return resolved

    raise ValueError(
        'Brave Search API key not found. Please provide an API key or set it in the environment variable BRAVE_WEB_SEARCH_API_KEY or in ~/.agentron/auth.json under the key "brave-web-search".'
    )
