import * as pi from '@mariozechner/pi-ai';

import type { Model } from '@ethereon/agentypes/model.js';

export function asPiModel(model: Model): pi.Model<pi.KnownApi> {
    return {
        id: model.id,
        name: model.name,
        api: model.api as pi.KnownApi,
        provider: model.provider,
        baseUrl: model.base_url,
        reasoning: model.reasoning,
        input: model.input,
        contextWindow: model.context_window,
        maxTokens: model.max_tokens,
        headers: model.headers,
        cost: {
            input: model.cost.input,
            output: model.cost.output,
            cacheRead: model.cost.cache_read,
            cacheWrite: model.cost.cache_write
        }
    };
}
