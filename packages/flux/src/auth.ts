import * as FS from 'node:fs/promises';
import * as Path from 'node:path';

import type { OAuthCredentials, OAuthProviderId } from '@mariozechner/pi-ai/oauth';
import type { OAuthLoginData } from './types/api.js';

export async function saveOAuthLoginData(
    providerId: OAuthProviderId,
    credentials: OAuthCredentials
): Promise<void> {
    // Load ~/.agentron/auth.json if it exists, otherwise start with an empty object
    let authData: Record<string, OAuthLoginData | string> = {};
    const homeDir = process.env.HOME;
    if (!homeDir) {
        throw new Error('HOME environment variable is not set.');
    }
    const authFile = Path.join(homeDir, '.agentron', 'auth.json');
    try {
        const content = await FS.readFile(authFile, 'utf-8');
        authData = JSON.parse(content);
        if (typeof authData !== 'object' || authData === null) {
            throw new Error(`Invalid auth file encountered at: ${authFile}`);
        }
    } catch (err) {
        if ((err as NodeJS.ErrnoException)?.code !== 'ENOENT') {
            throw err;
        }
    }

    // Add the new credentials
    authData[providerId] = { type: 'oauth', provider: providerId, credentials };

    // Save
    await FS.mkdir(Path.dirname(authFile), { recursive: true });
    await FS.writeFile(authFile, JSON.stringify(authData, null, 4), 'utf-8');
}
