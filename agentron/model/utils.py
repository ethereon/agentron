from typing import Sequence
from agentron.types.model import Model, ModelInputModality, ModelPricing, ModelApi


def make_model(
    *,
    name: str,
    url: str,
    id: str = '',
    provider: str = 'local',
    reasoning: bool = True,
    input: Sequence[ModelInputModality] = ('text', 'image'),
    api: ModelApi = 'openai-completions',
    max_tokens: int = 4096,
    context_window: int = 16384,
    cost: ModelPricing | None = None,
) -> Model:
    return Model(
        id=id or name,
        name=name,
        provider=provider,
        base_url=url,
        reasoning=reasoning,
        input=input,
        api=api,
        max_tokens=max_tokens,
        context_window=context_window,
        cost=cost or zero_cost(),
    )


def zero_cost() -> ModelPricing:
    return ModelPricing(input=0, output=0, cache_read=0, cache_write=0)
