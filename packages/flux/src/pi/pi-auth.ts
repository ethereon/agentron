import type { OAuthLoginData } from '@ethereon/agentypes/api.js';

import { getOAuthApiKey, type OAuthCredentials } from '@earendil-works/pi-ai/oauth';
import { saveOAuthLoginData } from '../auth.js';
import { isDeepEqual } from '@ethereon/ein/object';

export async function resolveApiKey(login: OAuthLoginData): Promise<string> {
    const result = await getOAuthApiKey(login.provider, {
        [login.provider]: login.credentials as OAuthCredentials
    });
    if (!result) {
        throw new Error(
            `Failed to retrieve API key for provider ${login.provider} (not logged in?)`
        );
    }
    if (result.newCredentials != null && !isDeepEqual(result.newCredentials, login.credentials)) {
        await saveOAuthLoginData(login.provider, result.newCredentials);
    }
    return result.apiKey;
}
