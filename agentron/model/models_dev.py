from __future__ import annotations

from typing import Literal, TypedDict

from agentron.model.types import Model, ModelApi, ModelPricing
from agentron.model.web_repo import WebModelRepo

MODELS_DEV_URL = 'https://models.dev/api.json'
FALLBACK_CONTEXT_WINDOW = 4096
FALLBACK_MAX_TOKENS = 4096


class ModelsDevLimits(TypedDict, total=False):
    context: int
    output: int


class ModelsDevPricing(TypedDict, total=False):
    input: float
    output: float
    cache_read: float
    cache_write: float


class ModelsDevModalities(TypedDict, total=False):
    input: list[str]
    output: list[str]


class ModelsDevModelData(TypedDict, total=False):
    name: str
    id: str
    api: str
    provider: str
    base_url: str
    limit: ModelsDevLimits
    cost: ModelsDevPricing
    modalities: ModelsDevModalities
    reasoning: bool
    headers: dict[str, str]
    tool_call: bool
    release_date: str


class ModelsDevProviderData(TypedDict, total=False):
    models: dict[str, ModelsDevModelData]


ModelsDevManifest = dict[str, ModelsDevProviderData]


class ModelsDevRepo(WebModelRepo[ModelsDevManifest]):
    def __init__(self) -> None:
        super().__init__(
            url=MODELS_DEV_URL,
            cache_name='models.dev.json',
        )

    def _find(self, provider: str, model: str) -> Model | None:
        assert self._manifest is not None

        provider_data = self._manifest.get(provider)
        if not isinstance(provider_data, dict):
            return None

        api = _API_MAP.get(provider_data.get('npm'))
        if api is None:
            return None

        base_url = _URL_MAP.get(provider) or provider_data.get('api')
        if base_url is None:
            return None

        models = provider_data.get('models')
        if not isinstance(models, dict):
            return None

        data = models.get(model)
        if not isinstance(data, dict):
            return None

        if not data.get('tool_call', False):
            return None

        limit = data.get('limit')
        modalities = data.get('modalities')
        return Model(
            api=api,
            base_url=base_url,
            id=_coerce_str(data.get('id'), default=model),
            name=_coerce_str(data.get('name'), default=model),
            provider=_coerce_str(data.get('provider'), default=provider),
            reasoning=bool(data.get('reasoning', False)),
            input=_translate_input_modalities(modalities),
            cost=_translate_cost(data.get('cost')),
            context_window=_coerce_int(limit.get('context') if isinstance(limit, dict) else FALLBACK_CONTEXT_WINDOW),
            max_tokens=_coerce_int(limit.get('output') if isinstance(limit, dict) else FALLBACK_MAX_TOKENS),
        )


def _translate_input_modalities(
    modalities: ModelsDevModalities | object,
) -> list[Literal['text', 'image']]:
    if not isinstance(modalities, dict):
        return []

    inputs = modalities.get('input')
    if not isinstance(inputs, list):
        return []

    translated: list[Literal['text', 'image']] = []
    for value in inputs:
        if value == 'text' or value == 'image':
            translated.append(value)
    return translated


def _translate_cost(pricing: ModelsDevPricing | object) -> ModelPricing:
    if not isinstance(pricing, dict):
        pricing = {}

    return {
        'input': _coerce_float(pricing.get('input')),
        'output': _coerce_float(pricing.get('output')),
        'cache_read': _coerce_float(pricing.get('cache_read')),
        'cache_write': _coerce_float(pricing.get('cache_write')),
    }


def _coerce_str(value: object, default: str) -> str:
    return value if isinstance(value, str) else default


def _coerce_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _coerce_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


_API_MAP: dict[str | None, ModelApi] = {
    None: 'openai-completions',
    '@ai-sdk/anthropic': 'anthropic-messages',
    '@ai-sdk/google': 'google-generative-ai',
    '@ai-sdk/openai-compatible': 'openai-completions',
    '@ai-sdk/openai': 'openai-responses',
    '@ai-sdk/amazon-bedrock': 'bedrock-converse-stream',
    '@ai-sdk/mistral': 'mistral-conversations',
}

_URL_MAP = {
    'amazon-bedrock': 'https://bedrock-runtime.us-east-1.amazonaws.com',
    'anthropic': 'https://api.anthropic.com',
    'google': 'https://generativelanguage.googleapis.com/v1beta',
    'openai': 'https://api.openai.com/v1',
    'groq': 'https://api.groq.com/openai/v1',
    'cerebras': 'https://api.cerebras.ai/v1',
    'xai': 'https://api.x.ai/v1',
    'mistral': 'https://api.mistral.ai',
}
