from __future__ import annotations

from typing import NotRequired, TypedDict

from agentron.model.types import Model, ModelInputModality, ModelPricing
from agentron.model.web_repo import WebModelRepo

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


class OpenRouterModelResponse(TypedDict):
    data: list[OpenRouterModelData]


class OpenRouterModelManifest(TypedDict):
    data: list[OpenRouterModelData]


class OpenRouterRepo(WebModelRepo[OpenRouterModelManifest]):
    def __init__(self) -> None:
        super().__init__(
            url='https://openrouter.ai/api/v1/models',
            cache_name='openrouter.json',
        )

    def _find(self, provider: str, model: str) -> Model | None:
        assert self._manifest is not None

        if provider != 'openrouter':
            return None

        for model_data in self._manifest['data']:
            if model_data['id'] == model or model_data['canonical_slug'] == model:
                return translate_model(model_data)
        return None

    def get_priority(self, provider: str) -> int:
        return 10 if provider == 'openrouter' else 0


def translate_model(data: OpenRouterModelData) -> Model:
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
        cost=translate_pricing(data.get('pricing')),
        context_window=data.get('context_length', FALLBACK_CONTEXT_WINDOW),
        max_tokens=data.get('top_provider', {}).get('max_completion_tokens', FALLBACK_MAX_TOKENS),
    )


def translate_pricing(pricing: OpenRouterPricing | None) -> ModelPricing:
    if pricing is None:
        return ModelPricing(input=0, output=0, cache_read=0, cache_write=0)
    return ModelPricing(
        input=convert_price(pricing.get('prompt')),
        output=convert_price(pricing.get('completion')),
        cache_read=convert_price(pricing.get('input_cache_read')),
        cache_write=convert_price(pricing.get('input_cache_write')),
    )


def convert_price(price_str: str | None) -> int:
    if price_str is None:
        return 0
    try:
        price = float(price_str)
        return int(price * 1_000_000)
    except ValueError:
        pass
    return 0
