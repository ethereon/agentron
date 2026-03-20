import type { Model, ModelReasoningLevel } from './model.js';

// --- AUTO-GENERATED CODE BELOW --- //

function isModelPricing(obj: any): boolean {
    return (
        obj != null &&
        typeof obj.input === 'number' &&
        typeof obj.output === 'number' &&
        typeof obj.cache_read === 'number' &&
        typeof obj.cache_write === 'number'
    );
}

export function isModel(obj: any): obj is Model {
    return (
        obj != null &&
        typeof obj.id === 'string' &&
        typeof obj.name === 'string' &&
        (obj.api === 'anthropic-messages' ||
            obj.api === 'azure-openai-responses' ||
            obj.api === 'bedrock-converse-stream' ||
            obj.api === 'google-gemini-cli' ||
            obj.api === 'google-generative-ai' ||
            obj.api === 'google-vertex' ||
            obj.api === 'mistral-conversations' ||
            obj.api === 'openai-codex-responses' ||
            obj.api === 'openai-completions' ||
            obj.api === 'openai-responses') &&
        typeof obj.provider === 'string' &&
        typeof obj.base_url === 'string' &&
        typeof obj.reasoning === 'boolean' &&
        Array.isArray(obj.input) &&
        obj.input.every((item: any) => item === 'text' || item === 'image') &&
        isModelPricing(obj.cost) &&
        typeof obj.context_window === 'number' &&
        typeof obj.max_tokens === 'number' &&
        (obj.headers == null ||
            (obj.headers != null &&
                typeof obj.headers === 'object' &&
                !Array.isArray(obj.headers) &&
                Object.values(obj.headers).every((value: any) => typeof value === 'string'))) &&
        (obj.auth_env_vars == null ||
            (Array.isArray(obj.auth_env_vars) &&
                obj.auth_env_vars.every((item: any) => typeof item === 'string')))
    );
}

export function isModelReasoningLevel(obj: any): obj is ModelReasoningLevel {
    return (
        obj === 'minimal' || obj === 'low' || obj === 'medium' || obj === 'high' || obj === 'xhigh'
    );
}
