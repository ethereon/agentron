import { describe, expect, it } from 'vitest';

import { extractBashCommands } from '../src/message/shell-parser.ts';

describe('extractBashCommands', () => {
    it('extracts command names from top-level separators', () => {
        expect(extractBashCommands('pnpm install && pnpm test; echo done\npwd')).toEqual([
            'pnpm',
            'pnpm',
            'echo',
            'pwd'
        ]);
    });

    it('skips env and environment assignments before the command', () => {
        expect(extractBashCommands('env FOO=bar BAR=baz /usr/bin/python script.py')).toEqual([
            'python'
        ]);
    });

    it('does not split on separators inside quotes or command substitution', () => {
        expect(
            extractBashCommands('printf \'a|b;c\' && echo $(node -p "1 + 1") && test "$x" = "a;b"')
        ).toEqual(['printf', 'echo', 'test']);
    });

    it('treats pipelines as separate top-level commands', () => {
        expect(extractBashCommands('cat file.txt | grep needle | sort')).toEqual([
            'cat',
            'grep',
            'sort'
        ]);
    });

    it('ignores command-like text inside here-doc bodies', () => {
        expect(
            extractBashCommands(
                ["cat <<'EOF'", 'echo hidden', 'grep also-hidden', 'EOF', 'printf done'].join('\n')
            )
        ).toEqual(['cat', 'printf']);
    });

    it('supports tab-indented here-doc terminators', () => {
        expect(
            extractBashCommands(['cat <<-EOF', '\tcontent', '\tEOF', 'wc -l file.txt'].join('\n'))
        ).toEqual(['cat', 'wc']);
    });
});
