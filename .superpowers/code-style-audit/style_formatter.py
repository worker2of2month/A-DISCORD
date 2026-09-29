"""Conservative token-preserving formatter for an isolated style audit."""
from dataclasses import dataclass
import re

TOKEN = re.compile(r'"(?:\\[\s\S]|[^"\\])*"|\#[^\r\n]*|<=|>=|!=|==|\?=|\+=|-=|[{}=<>]|[^\s{}=<>#"]+')
OPERATORS = {'=', '<', '>', '<=', '>=', '!=', '==', '?=', '+=', '-='}
PARAMETER_BLOCKS = {
    'check_variable', 'check_temp_variable', 'set_variable', 'set_temp_variable',
    'add_to_variable', 'add_to_temp_variable', 'subtract_from_variable',
    'subtract_from_temp_variable', 'multiply_variable', 'multiply_temp_variable',
    'divide_variable', 'divide_temp_variable', 'clamp_variable', 'clamp_temp_variable',
    'round_variable', 'round_temp_variable', 'country_event', 'news_event', 'state_event',
    'add_equipment_to_stockpile', 'add_building_construction', 'remove_building',
    'set_building_level', 'declare_war_on', 'create_wargoal', 'load_focus_tree',
    'set_autonomy', 'set_politics', 'set_technology', 'set_power_balance',
    'add_to_array', 'remove_from_array', 'is_in_array', 'export_to_variable',
    'position', 'size', 'minSize', 'maxSize', 'borderSize', 'stepSize',
    'continuous_focus_position', 'color', 'colour', 'font_color',
}
DIRECTIVES = ('# @include ', '# @section ')

@dataclass
class Token:
    kind: str
    text: str
    line: int
    end_line: int

@dataclass
class Group:
    children: list
    opening: Token
    closing: Token
    key: str

    @property
    def line(self):
        return self.opening.line

    @property
    def end_line(self):
        return self.closing.end_line

def lex(source):
    if source.startswith('\ufeff'):
        source = source[1:]
    tokens = []
    cursor = 0
    line = 1
    for match in TOKEN.finditer(source):
        gap = source[cursor:match.start()]
        if gap.strip():
            raise ValueError(f'Unrecognized or unterminated token on line {line}: {gap[:80]!r}')
        line += gap.count('\n')
        raw = match.group()
        kind = 'word'
        if raw.startswith('"'):
            kind = 'string'
        elif raw.startswith('#'):
            kind = 'comment'
            raw = raw.rstrip(' \t')
        elif raw in OPERATORS:
            kind = 'operator'
        elif raw in {'{', '}'}:
            kind = raw
        end_line = line + match.group().count('\n')
        tokens.append(Token(kind, raw, line, end_line))
        line = end_line
        cursor = match.end()
    if source[cursor:].strip():
        raise ValueError(f'Unrecognized or unterminated token on line {line}')
    return tokens

def token_signature(source):
    return tuple((token.kind, token.text) for token in lex(source))

def parse_groups(tokens):
    def consume(index, opening=None, key=''):
        children = []
        while index < len(tokens):
            token = tokens[index]
            if token.kind == '}':
                if opening is None:
                    raise ValueError(f'Unexpected closing brace on line {token.line}')
                return Group(children, opening, token, key), index + 1
            if token.kind == '{':
                child_key = ''
                if len(children) >= 2 and isinstance(children[-1], Token) and children[-1].kind == 'operator':
                    child_key = children[-2].text if isinstance(children[-2], Token) else ''
                elif len(children) >= 3 and isinstance(children[-2], Token) and children[-2].kind == 'operator':
                    child_key = children[-3].text if isinstance(children[-3], Token) else ''
                group, index = consume(index + 1, token, child_key)
                children.append(group)
            else:
                children.append(token)
                index += 1
        if opening is not None:
            raise ValueError(f'Unclosed brace on line {opening.line}')
        return children, index
    return consume(0)[0]

def inline_group(group, depth):
    if group.line != group.end_line:
        return None
    if any(isinstance(node, Group) or node.kind == 'comment' for node in group.children):
        return None
    fields = sum(node.kind == 'operator' for node in group.children)
    if fields > 1 and group.key not in PARAMETER_BLOCKS:
        return None
    content = ' '.join(node.text for node in group.children)
    result = '{ ' + content + ' }' if content else '{ }'
    if fields > 1 and depth * 4 + len(group.key) + 3 + len(result) > 120:
        return None
    if fields == 0 and depth * 4 + len(result) > 120:
        return None
    return result

def format_clausewitz(source, *, base_indent=0):
    tokens = lex(source)
    if not tokens:
        return ''
    nodes = parse_groups(tokens)
    def render(items, depth, opening_line=0, top=False):
        output = []
        buffer = []
        previous_end = opening_line
        previous_was_definition = False
        current_definition = False
        def flush():
            nonlocal current_definition, previous_was_definition
            if buffer:
                output.append('\t' * depth + ' '.join(buffer).rstrip(' \t'))
                buffer.clear()
                previous_was_definition = current_definition
                current_definition = False
        def blank():
            if output and output[-1] != '':
                output.append('')
        for index, node in enumerate(items):
            next_node = items[index + 1] if index + 1 < len(items) else None
            header = isinstance(node, Token) and node.kind in {'word', 'string'} and isinstance(next_node, Token) and next_node.kind == 'operator'
            comment = isinstance(node, Token) and node.kind == 'comment'
            gap = node.line - previous_end
            if comment:
                if node.line == previous_end and (buffer or (output and output[-1])):
                    if buffer:
                        buffer.append(node.text)
                        flush()
                    else:
                        output[-1] += ' ' + node.text
                else:
                    flush()
                    if gap > 1 or (top and previous_was_definition):
                        blank()
                    previous_was_definition = False
                    indent = 0 if node.text.startswith(DIRECTIVES) else depth
                    output.append('\t' * indent + node.text)
                previous_end = node.end_line
                continue
            if header:
                flush()
                if gap > 1 or (top and previous_was_definition):
                    blank()
            elif gap > 0 and buffer:
                awaiting_value = buffer[-1] in OPERATORS
                next_is_operator = isinstance(node, Token) and node.kind == 'operator'
                if not awaiting_value and not next_is_operator and not isinstance(node, Group):
                    flush()
                    if gap > 1:
                        blank()
            elif not buffer and gap > 1:
                blank()
            if isinstance(node, Group):
                compact = inline_group(node, depth)
                if compact is not None:
                    buffer.append(compact)
                    current_definition = True
                else:
                    buffer.append('{')
                    flush()
                    body = render(node.children, depth + 1, node.line)
                    while body and body[-1] == '':
                        body.pop()
                    output.extend(body)
                    buffer.append('}')
                    current_definition = True
            else:
                if not header and node.kind == 'word' and buffer and all(value not in OPERATORS for value in buffer):
                    if depth * 4 + sum(len(value) + 1 for value in buffer) + len(node.text) > 120:
                        flush()
                buffer.append(node.text)
            previous_end = node.end_line
        flush()
        while output and output[-1] == '':
            output.pop()
        return output
    formatted = '\n'.join(render(nodes, base_indent, top=True)) + '\n'
    if token_signature(source) != token_signature(formatted):
        raise ValueError('Formatting changed the ordered token sequence')
    return formatted

def format_localisation(source):
    if source.startswith('\ufeff'):
        source = source[1:]
    output = []
    in_language = False
    for number, line in enumerate(source.splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            if output and output[-1] != '':
                output.append('')
            continue
        if stripped.startswith('#'):
            output.append((' ' if in_language else '') + stripped)
            continue
        if re.fullmatch(r'l_[a-z_]+:', stripped):
            output.append(stripped)
            in_language = True
            continue
        match = re.match(r'^[ \t]*([^:#\s]+):(\d*)[ \t]*("(?:\\.|[^"\\])*"?)(.*)$', line)
        if not match or not match[3].endswith('"') or (match[4].strip() and not match[4].lstrip().startswith('#')):
            raise ValueError(f'Malformed or multiline localisation entry on line {number}')
        suffix = ' ' + match[4].strip() if match[4].strip() else ''
        output.append(f' {match[1]}:{match[2]} {match[3]}{suffix}')
    while output and not output[-1]:
        output.pop()
    return '\n'.join(output) + ('\n' if output else '')

def format_lua_defines(source):
    output = []
    depth = 0
    quoted = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')
    for number, line in enumerate(source.splitlines(), 1):
        stripped = line.lstrip(' \t').rstrip(' \t')
        if not stripped:
            if output and output[-1] != '':
                output.append('')
            continue
        code = quoted.sub('STRING', stripped).split('--', 1)[0].strip()
        indent = depth - int(code.startswith('}'))
        if indent < 0:
            raise ValueError(f'Unexpected closing Lua table on line {number}')
        output.append('\t' * indent + stripped)
        depth += code.count('{') - code.count('}')
    if depth:
        raise ValueError('Unbalanced Lua table')
    while output and not output[-1]:
        output.pop()
    return '\n'.join(output) + ('\n' if output else '')
