// Auto-generated file. Do not edit directly.

export interface ModelPricing {
    input: number;
    output: number;
    cache_read: number;
    cache_write: number;
}

export const enum ModelApi {
    ANTHROPIC_MESSAGES = 'anthropic-messages',
    AZURE_OPENAI_RESPONSES = 'azure-openai-responses',
    BEDROCK_CONVERSE_STREAM = 'bedrock-converse-stream',
    GOOGLE_GEMINI_CLI = 'google-gemini-cli',
    GOOGLE_GENERATIVE_AI = 'google-generative-ai',
    GOOGLE_VERTEX = 'google-vertex',
    MISTRAL_CONVERSATIONS = 'mistral-conversations',
    OPENAI_CODEX_RESPONSES = 'openai-codex-responses',
    OPENAI_COMPLETIONS = 'openai-completions',
    OPENAI_RESPONSES = 'openai-responses'
}

export const enum ModelInputModality {
    TEXT = 'text',
    IMAGE = 'image'
}

export interface Model {
    id: string;
    name: string;
    api: ModelApi;
    provider: string;
    base_url: string;
    reasoning: boolean;
    input: ModelInputModality[];
    cost: ModelPricing;
    context_window: number;
    max_tokens: number;
    headers?: Record<string, string>;
}

export const enum ModelReasoningLevel {
    DISABLED = 'disabled',
    LOW = 'low',
    MEDIUM = 'medium',
    HIGH = 'high',
    EXTRA_HIGH = 'extra_high'
}
