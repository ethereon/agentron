from typing import Literal, Sequence, TypedDict, NotRequired
from enum import StrEnum


class ModelPricing(TypedDict):
    input: float
    output: float
    cache_read: float
    cache_write: float


class ModelApi(StrEnum):
    ANTHROPIC_MESSAGES = 'anthropic-messages'
    AZURE_OPENAI_RESPONSES = 'azure-openai-responses'
    BEDROCK_CONVERSE_STREAM = 'bedrock-converse-stream'
    GOOGLE_GEMINI_CLI = 'google-gemini-cli'
    GOOGLE_GENERATIVE_AI = 'google-generative-ai'
    GOOGLE_VERTEX = 'google-vertex'
    MISTRAL_CONVERSATIONS = 'mistral-conversations'
    OPENAI_CODEX_RESPONSES = 'openai-codex-responses'
    OPENAI_COMPLETIONS = 'openai-completions'
    OPENAI_RESPONSES = 'openai-responses'


class ModelInputModality(StrEnum):
    TEXT = 'text'
    IMAGE = 'image'


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


class ModelReasoningLevel(StrEnum):
    DISABLED = 'disabled'
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    EXTRA_HIGH = 'extra_high'
