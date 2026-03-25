import type { OAuthLoginData } from '../api.js';

import { getOAuthApiKey, type OAuthCredentials } from '@mariozechner/pi-ai/oauth';
import { saveOAuthLoginData } from '../auth.js';

export async function resolveApiKey(login: OAuthLoginData): Promise<string> {
    const result = await getOAuthApiKey(login.provider, {
        [login.provider]: login.credentials as OAuthCredentials
    });
    if (!result) {
        throw new Error(
            `Failed to retrieve API key for provider ${login.provider} (not logged in?)`
        );
    }
    if (
        result.newCredentials != null &&
        JSON.stringify(result.newCredentials) !== JSON.stringify(login.credentials)
    ) {
        await saveOAuthLoginData(login.provider, result.newCredentials);
    }
    return result.apiKey;
}
