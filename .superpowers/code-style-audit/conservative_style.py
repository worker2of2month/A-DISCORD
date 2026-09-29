"""Normalize indentation without rewriting line-sensitive source contracts."""
from collections import defaultdict
from style_formatter import lex, parse_groups, token_signature, DIRECTIVES


def format_clausewitz(source, *, base_indent=0):
    tokens = lex(source)
    parse_groups(tokens)
    if not source:
        return ''
    by_line = defaultdict(list)
    protected_lines = set()
    multiline_starts = set()
    for token in tokens:
        by_line[token.line].append(token)
        if token.kind == 'string' and token.end_line > token.line:
            multiline_starts.add(token.line)
            protected_lines.update(range(token.line + 1, token.end_line + 1))
    output = []
    depth = 0
    for number, line in enumerate(source.splitlines(), 1):
        line_tokens = by_line[number]
        leading_closers = 0
        for token in line_tokens:
            if token.kind != '}':
                break
            leading_closers += 1
        if number in protected_lines:
            output.append(line)
        elif not line.strip():
            output.append('')
        else:
            content = line.lstrip(' \t')
            if number not in multiline_starts:
                content = content.rstrip(' \t')
            indent = base_indent + depth - leading_closers
            if content.startswith(DIRECTIVES):
                indent = 0
            if indent < 0:
                raise ValueError(f'Negative indentation on line {number}')
            output.append('\t' * indent + content)
        depth += sum(token.kind == '{' for token in line_tokens)
        depth -= sum(token.kind == '}' for token in line_tokens)
    if depth:
        raise ValueError('Unbalanced source')
    result = '\n'.join(output) + '\n'
    if token_signature(source) != token_signature(result):
        raise ValueError('Indentation changed the ordered token sequence')
    return result
