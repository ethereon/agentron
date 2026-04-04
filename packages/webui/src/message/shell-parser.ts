export function extractBashCommands(command: string): string[] {
    const segments: string[] = [];
    let current = '';
    let quote: "'" | '"' | null = null;
    let parenDepth = 0;
    let bracketDepth = 0;
    let braceDepth = 0;
    let escaped = false;
    const hereDocs: HereDoc[] = [];
    let atLineStart = true;

    for (let index = 0; index < command.length; index += 1) {
        const char = command[index];
        const nextChar = command[index + 1];
        const activeHereDoc = hereDocs[0] ?? null;

        if (activeHereDoc != null && atLineStart) {
            const terminatorLength = matchHereDocTerminator(command, index, activeHereDoc);
            if (terminatorLength > 0) {
                current += command.slice(index, index + terminatorLength);
                hereDocs.shift();
                index += terminatorLength - 1;
                atLineStart = false;
                continue;
            }
        }

        if (activeHereDoc != null) {
            current += char;
            atLineStart = char === '\n';
            continue;
        }

        if (escaped) {
            current += char;
            escaped = false;
            atLineStart = char === '\n';
            continue;
        }

        if (char === '\\') {
            current += char;
            escaped = true;
            atLineStart = false;
            continue;
        }

        if (quote != null) {
            if (quote === '"' && char === '\\' && nextChar != null) {
                current += char;
                current += nextChar;
                index += 1;
                atLineStart = false;
                continue;
            }

            current += char;
            if (char === quote) {
                quote = null;
            }
            atLineStart = char === '\n';
            continue;
        }

        if (char === "'" || char === '"') {
            current += char;
            quote = char;
            atLineStart = false;
            continue;
        }

        const isTopLevel = parenDepth === 0 && bracketDepth === 0 && braceDepth === 0;

        if (isTopLevel && char === '<' && nextChar === '<') {
            const hereDoc = readHereDoc(command, index);
            if (hereDoc != null) {
                current += command.slice(index, hereDoc.endIndex);
                hereDocs.push({
                    delimiter: hereDoc.delimiter,
                    allowIndentedTabs: hereDoc.allowIndentedTabs
                });
                index = hereDoc.endIndex - 1;
                atLineStart = false;
                continue;
            }
        }

        if (char === '(') {
            current += char;
            parenDepth += 1;
            atLineStart = false;
            continue;
        }

        if (char === ')' && parenDepth > 0) {
            current += char;
            parenDepth -= 1;
            atLineStart = false;
            continue;
        }

        if (char === '[') {
            current += char;
            bracketDepth += 1;
            atLineStart = false;
            continue;
        }

        if (char === ']' && bracketDepth > 0) {
            current += char;
            bracketDepth -= 1;
            atLineStart = false;
            continue;
        }

        if (char === '{') {
            current += char;
            braceDepth += 1;
            atLineStart = false;
            continue;
        }

        if (char === '}' && braceDepth > 0) {
            current += char;
            braceDepth -= 1;
            atLineStart = false;
            continue;
        }

        const isBooleanSeparator =
            isTopLevel &&
            ((char === '&' && nextChar === '&') || (char === '|' && nextChar === '|'));
        const isStatementSeparator = isTopLevel && (char === ';' || char === '\n' || char === '|');

        if (isBooleanSeparator) {
            pushIfPresent(segments, current);
            current = '';
            index += 1;
            atLineStart = false;
            continue;
        }

        if (char === '\n' && hereDocs.length > 0) {
            current += char;
            atLineStart = true;
            continue;
        }

        if (isStatementSeparator) {
            pushIfPresent(segments, current);
            current = '';
            atLineStart = true;
            continue;
        }

        current += char;
        atLineStart = false;
    }

    pushIfPresent(segments, current);

    return segments.map(extractCommandName).filter((name): name is string => name != null);
}

function pushIfPresent(values: string[], value: string): void {
    const trimmed = value.trim();
    if (trimmed.length > 0) {
        values.push(trimmed);
    }
}

function extractCommandName(segment: string): string | null {
    const tokens = tokenizeShellWords(segment);
    if (tokens.length === 0) {
        return null;
    }

    let index = 0;
    while (index < tokens.length) {
        const token = tokens[index];
        if (token === 'env') {
            index += 1;
            continue;
        }

        if (isEnvironmentAssignment(token)) {
            index += 1;
            continue;
        }

        return normalizeCommandName(token);
    }

    return null;
}

function tokenizeShellWords(segment: string): string[] {
    const tokens: string[] = [];
    let current = '';
    let quote: "'" | '"' | null = null;
    let escaped = false;

    for (let index = 0; index < segment.length; index += 1) {
        const char = segment[index];

        if (escaped) {
            current += char;
            escaped = false;
            continue;
        }

        if (char === '\\') {
            escaped = true;
            continue;
        }

        if (quote != null) {
            if (quote === '"' && char === '\\' && index + 1 < segment.length) {
                current += segment[index + 1];
                index += 1;
                continue;
            }

            if (char === quote) {
                quote = null;
            } else {
                current += char;
            }
            continue;
        }

        if (char === "'" || char === '"') {
            quote = char;
            continue;
        }

        if (/\s/.test(char)) {
            if (current.length > 0) {
                tokens.push(current);
                current = '';
            }
            continue;
        }

        current += char;
    }

    if (current.length > 0) {
        tokens.push(current);
    }

    return tokens;
}

function isEnvironmentAssignment(token: string): boolean {
    return /^[A-Za-z_][A-Za-z0-9_]*=/.test(token);
}

function normalizeCommandName(token: string): string {
    const command = token.split('/').at(-1) ?? token;
    return command.trim();
}

type HereDoc = {
    delimiter: string;
    allowIndentedTabs: boolean;
};

function readHereDoc(
    command: string,
    startIndex: number
): { delimiter: string; allowIndentedTabs: boolean; endIndex: number } | null {
    let index = startIndex + 2;
    let allowIndentedTabs = false;

    if (command[index] === '-') {
        allowIndentedTabs = true;
        index += 1;
    }

    while (command[index] === ' ' || command[index] === '\t') {
        index += 1;
    }

    if (index >= command.length) {
        return null;
    }

    const delimiter = readHereDocDelimiter(command, index);
    if (delimiter == null) {
        return null;
    }

    return {
        delimiter: delimiter.value,
        allowIndentedTabs,
        endIndex: delimiter.endIndex
    };
}

function readHereDocDelimiter(
    command: string,
    startIndex: number
): { value: string; endIndex: number } | null {
    const startChar = command[startIndex];

    if (startChar === "'") {
        const endIndex = command.indexOf("'", startIndex + 1);
        if (endIndex === -1) {
            return null;
        }

        return {
            value: command.slice(startIndex + 1, endIndex),
            endIndex: endIndex + 1
        };
    }

    if (startChar === '"') {
        let value = '';

        for (let index = startIndex + 1; index < command.length; index += 1) {
            const char = command[index];

            if (char === '\\' && index + 1 < command.length) {
                value += command[index + 1];
                index += 1;
                continue;
            }

            if (char === '"') {
                return {
                    value,
                    endIndex: index + 1
                };
            }

            value += char;
        }

        return null;
    }

    let value = '';
    let index = startIndex;

    while (index < command.length) {
        const char = command[index];
        if (/\s/.test(char)) {
            break;
        }

        if (char === '\\' && index + 1 < command.length) {
            value += command[index + 1];
            index += 2;
            continue;
        }

        value += char;
        index += 1;
    }

    if (value.length === 0) {
        return null;
    }

    return { value, endIndex: index };
}

function matchHereDocTerminator(command: string, startIndex: number, hereDoc: HereDoc): number {
    let lineEnd = command.indexOf('\n', startIndex);
    if (lineEnd === -1) {
        lineEnd = command.length;
    }

    const line = command.slice(startIndex, lineEnd);
    if (line === hereDoc.delimiter) {
        return line.length;
    }

    if (!hereDoc.allowIndentedTabs) {
        return 0;
    }

    const trimmedLine = line.replace(/^\t+/, '');
    if (
        trimmedLine === hereDoc.delimiter &&
        /^\t*$/.test(line.slice(0, line.length - trimmedLine.length))
    ) {
        return line.length;
    }

    return 0;
}
