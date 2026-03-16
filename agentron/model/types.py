from typing import Sequence, TypedDict, NotRequired, Literal


type ModelApi = Literal[
    'anthropic-messages',
    'azure-openai-responses',
    'bedrock-converse-stream',
    'google-gemini-cli',
    'google-generative-ai',
    'google-vertex',
    'mistral-conversations',
    'openai-codex-responses',
    'openai-completions',
    'openai-responses',
]

type ModelInputModality = Literal[
    'text',
    'image',
]

type ModelReasoningLevel = Literal[
    'minimal',
    'low',
    'medium',
    'high',
    'xhigh',
]


class ModelPricing(TypedDict):
    input: float
    output: float
    cache_read: float
    cache_write: float


class Model(TypedDict):
    id: str
    name: str
    api: ModelApi
    provider: str
    base_url: str
    reasoning: bool
    input: Sequence[ModelInputModality]
    cost: ModelPricing
    context_window: int
    max_tokens: int
    headers: NotRequired[dict[str, str]]
