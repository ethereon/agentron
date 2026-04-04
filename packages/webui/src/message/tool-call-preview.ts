import { ToolCall } from '@ethereon/agentypes/messages.js';
import { extractBashCommands } from './shell-parser.js';

const TRIVIAL_BASH_COMMANDS = new Set(['cd']);

export function resolveToolCallPreview(toolCall: ToolCall): string | null {
    const args = toolCall.arguments;
    switch (toolCall.name) {
        case 'bash':
            return generateBashPreview(args.command as string);

        default:
            // Default: check for path arguments
            const path = args?.path;
            if (typeof path === 'string') {
                return path.split('/').at(-1)!.trim();
            }
    }
    return null;
}

function generateBashPreview(command: string): string | null {
    if (command == null) {
        return null;
    }

    const commands = extractBashCommands(command);
    if (commands.length === 0) {
        return null;
    }

    const significantCommands = commands.filter(
        name => !TRIVIAL_BASH_COMMANDS.has(name.toLowerCase())
    );
    const previewCommands = significantCommands.length > 0 ? significantCommands : commands;
    return previewCommands.join(', ');
}
