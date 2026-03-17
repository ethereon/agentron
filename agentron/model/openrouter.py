from __future__ import annotations

from typing import NotRequired, TypedDict

from agentron.model.types import Model, ModelInputModality, ModelPricing
from agentron.model.web_repo import WebModelRepo, MetadataFetchError

FALLBACK_CONTEXT_WINDOW = 4096
FALLBACK_MAX_TOKENS = 4096


class OpenRouterModelData(TypedDict):
    # eg: 'anthropic/claude-opus-4.1'
    id: str
    # eg: 'anthropic/claude-4.1-opus-20250805'
    canonical_slug: str
    # 'Anthropic: Claude Opus 4.1'
    name: str
    # eg:  'Claude Opus 4.1 is an updated version of Anthropic's...'
    description: NotRequired[str]
    # eg: 200000
    context_length: NotRequired[int]
    # eg: ['tools', 'max_tokens', 'temperature', ...]
    supported_parameters: NotRequired[list[str]]
    # eg: { modality: 'text+image->text+image' ... }
    architecture: NotRequired[OpenRouterArchitecture]
    # eg: { prompt: '0.0000003', completion: '0.0000025', ... }
    pricing: NotRequired[OpenRouterPricing]
    # eg: { context_length: 131072, max_completion_tokens: 131072, ... }
    top_provider: NotRequired[OpenRouterTopProvider]


class OpenRouterArchitecture(TypedDict, total=False):
    # eg: 'text+image->text+image'
    modality: str


# Each value is a string representation of a floating point number,
# with the units $/token.
class OpenRouterPricing(TypedDict, total=False):
    prompt: str
    completion: str
    image: str
    audio: str
    internal_reasoning: str
    input_cache_read: str
    input_cache_write: str


class OpenRouterTopProvider(TypedDict, total=False):
    context_length: int
    max_completion_tokens: int


type OpenRouterModelManifest = list[OpenRouterModelData]


class OpenRouterRepo(WebModelRepo[OpenRouterModelManifest]):
    def __init__(self) -> None:
        super().__init__(
            url='https://openrouter.ai/api/v1/models',
            cache_name='openrouter.json',
        )

    def get_priority(self, provider: str) -> int:
        return 10 if provider == 'openrouter' else 0

    def _find(self, provider: str, model: str) -> Model | None:
        assert self._manifest is not None

        if provider != 'openrouter':
            # Raise a LookupError rather than return None to prevent the
            # base class from attempting to scan again using a refreshed manifest.
            raise LookupError(f'Provider "{provider}" not supported by OpenRouterRepo.')

        for model_data in self._manifest:
            if model_data['id'] == model or model_data['canonical_slug'] == model:
                return _translate_model(model_data)
        return None

    def _transform_payload(self, data):
        # Unwrap from the outer {data: ...} envelope
        if not isinstance(data, dict):
            raise MetadataFetchError('OpenRouter manifest has incorrect type.')

        entries = data.get('data')
        if not isinstance(entries, list):
            raise MetadataFetchError('OpenRouter manifest has invalid data list.')

        return entries

    def _filter_validated(self, data: OpenRouterModelManifest) -> OpenRouterModelManifest:
        # Constrain to models that support tool calls
        return list(filter(_supports_tool_call, data))


def _supports_tool_call(model: OpenRouterModelData) -> bool:
    params = model.get('supported_parameters')
    return isinstance(params, list) and 'tools' in params


def _translate_model(data: OpenRouterModelData) -> Model:
    input_modalities: list[ModelInputModality] = ['text']
    if 'image' in data.get('architecture', {}).get('modality', ''):
        input_modalities.append('image')

    return Model(
        id=data['id'],
        name=data['name'],
        api='openai-completions',
        provider='openrouter',
        base_url='https://openrouter.ai/api/v1',
        reasoning=('reasoning' in data.get('supported_parameters', ())),
        input=input_modalities,
        cost=_translate_pricing(data.get('pricing')),
        context_window=data.get('context_length', FALLBACK_CONTEXT_WINDOW),
        max_tokens=data.get('top_provider', {}).get('max_completion_tokens', FALLBACK_MAX_TOKENS),
    )


def _translate_pricing(pricing: OpenRouterPricing | None) -> ModelPricing:
    if pricing is None:
        return ModelPricing(input=0, output=0, cache_read=0, cache_write=0)
    return ModelPricing(
        input=_convert_price(pricing.get('prompt')),
        output=_convert_price(pricing.get('completion')),
        cache_read=_convert_price(pricing.get('input_cache_read')),
        cache_write=_convert_price(pricing.get('input_cache_write')),
    )


def _convert_price(price_str: str | None) -> float:
    if price_str is None:
        return 0
    try:
        # Convert from $/token to $/million tokens
        return float(price_str) * 1_000_000
    except ValueError:
        pass
    return 0
