// Auto-generated file. Do not edit directly.

export type ModelApi =
    | 'anthropic-messages'
    | 'azure-openai-responses'
    | 'bedrock-converse-stream'
    | 'google-gemini-cli'
    | 'google-generative-ai'
    | 'google-vertex'
    | 'mistral-conversations'
    | 'openai-codex-responses'
    | 'openai-completions'
    | 'openai-responses';

export type ModelInputModality = 'text' | 'image';

export type ModelReasoningLevel = 'minimal' | 'low' | 'medium' | 'high' | 'xhigh';

export interface ModelPricing {
    input: number;
    output: number;
    cache_read: number;
    cache_write: number;
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
    auth_env_vars?: string[];
}
