"""Minimal YAML subset parser/emitter for the controlled schemas used by
knowledge/rules/*.yaml and knowledge/errors/*.yaml.

Supported subset:
- nested mappings via 2-space indentation
- scalar values (str / int / float / bool), quoted or plain
- block scalars:  key: >   (folded)  and  key: |  (literal)
- lists of scalars (- item) and lists of mappings (- key: value ...)
- flow lists [a, b, c]
- full-line comments (#) and blank lines

This avoids a PyYAML dependency while remaining file-compatible with the
YAML documents in this repository.
"""

from __future__ import annotations

import re


class YamlLiteError(ValueError):
    pass


def _parse_scalar(token: str):
    token = token.strip()
    if token == "":
        return ""
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"'):
        return token[1:-1]
    low = token.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~", "none"):
        return None
    if token.startswith("[") and token.endswith("]"):
        inner = token[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part) for part in _split_flow(inner)]
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        pass
    return token


def _split_flow(inner: str):
    parts, depth, quote, cur = [], 0, None, []
    for ch in inner:
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            cur.append(ch)
        elif ch in "[{":
            depth += 1
            cur.append(ch)
        elif ch in "]}":
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip() != ""]


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


# a list item is a mapping only when it starts with a plain key + colon,
# e.g. "- name: x"; text containing colons elsewhere stays a scalar
_KEY_ITEM_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*:(\s|$)")


def parse(text: str):
    lines = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        # strip trailing comment on plain scalar lines (outside quotes)
        stripped = raw.rstrip()
        lines.append(stripped)
    value, idx = _parse_block(lines, 0, 0)
    return value


def _parse_block(lines, idx: int, indent: int):
    """Parse a block starting at lines[idx] with the given indentation.
    Returns (value, next_index)."""
    if idx >= len(lines):
        return None, idx
    line = lines[idx]
    if _indent_of(line) < indent:
        return None, idx
    if line.lstrip().startswith("- "):
        return _parse_list(lines, idx, _indent_of(line))
    return _parse_map(lines, idx, _indent_of(line))


def _parse_map(lines, idx: int, indent: int):
    result = {}
    while idx < len(lines):
        line = lines[idx]
        cur = _indent_of(line)
        if cur < indent or line.lstrip().startswith("- "):
            break
        if cur > indent:
            raise YamlLiteError("unexpected indent at line: %r" % line)
        content = line.strip()
        if ":" not in content:
            raise YamlLiteError("expected 'key: value' at line: %r" % line)
        key, _, rest = content.partition(":")
        key = key.strip()
        rest = rest.strip()
        if rest in (">", "|", ">-", "|-"):
            block, idx = _collect_block_scalar(lines, idx + 1, indent, fold=(rest[0] == ">"))
            result[key] = block
            continue
        if rest == "":
            # nested block (map or list) or empty value
            if idx + 1 < len(lines) and _indent_of(lines[idx + 1]) > indent:
                value, idx = _parse_block(lines, idx + 1, _indent_of(lines[idx + 1]))
                result[key] = value
                continue
            result[key] = None
            idx += 1
            continue
        result[key] = _parse_scalar(rest)
        idx += 1
    return result, idx


def _parse_list(lines, idx: int, indent: int):
    result = []
    while idx < len(lines):
        line = lines[idx]
        cur = _indent_of(line)
        if cur != indent or not line.lstrip().startswith("-"):
            break
        item = line.lstrip()[1:].strip()
        if item == "":
            # nested block item
            if idx + 1 < len(lines) and _indent_of(lines[idx + 1]) > indent:
                value, idx = _parse_block(lines, idx + 1, _indent_of(lines[idx + 1]))
                result.append(value)
                continue
            result.append(None)
            idx += 1
            continue
        if _KEY_ITEM_RE.match(item):
            # mapping item starting on the dash line
            sub_indent = cur + 2
            synthetic = [" " * sub_indent + item]
            j = idx + 1
            while j < len(lines) and _indent_of(lines[j]) >= sub_indent \
                    and not lines[j].lstrip().startswith("- "):
                synthetic.append(lines[j])
                j += 1
            value, _ = _parse_map(synthetic, 0, sub_indent)
            result.append(value)
            idx = j
            continue
        result.append(_parse_scalar(item))
        idx += 1
        # continuation lines: deeper-indented plain text belongs to this item
        cont = []
        while idx < len(lines):
            nxt = lines[idx]
            if _indent_of(nxt) <= indent or nxt.lstrip().startswith("- "):
                break
            cont.append(nxt.strip())
            idx += 1
        if cont and isinstance(result[-1], str):
            result[-1] = result[-1] + " " + " ".join(cont)
    return result, idx


def _collect_block_scalar(lines, idx: int, parent_indent: int, fold: bool):
    chunks = []
    block_indent = None
    while idx < len(lines):
        line = lines[idx]
        cur = _indent_of(line)
        if cur <= parent_indent:
            break
        if block_indent is None:
            block_indent = cur
        chunks.append(line[block_indent:])
        idx += 1
    joiner = " " if fold else "\n"
    return joiner.join(chunks).strip("\n"), idx


# ---------------------------------------------------------------- emitter

def dump(obj, indent: int = 0) -> str:
    pad = "  " * indent
    out = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, (dict, list)) and value:
                out.append("%s%s:" % (pad, key))
                out.append(dump(value, indent + 1).rstrip("\n"))
            elif isinstance(value, str) and ("\n" in value):
                out.append("%s%s: |" % (pad, key))
                for ln in value.splitlines():
                    out.append("%s  %s" % (pad, ln))
            else:
                out.append("%s%s: %s" % (pad, key, _emit_scalar(value)))
        return "\n".join(out) + "\n"
    if isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                lines = dump(item, indent + 1).rstrip("\n").split("\n")
                first = lines[0].strip()
                out.append("%s- %s" % (pad, first))
                out.extend(lines[1:])
            elif isinstance(item, list):
                out.append("%s-" % pad)
                out.append(dump(item, indent + 1).rstrip("\n"))
            else:
                out.append("%s- %s" % (pad, _emit_scalar(item)))
        return "\n".join(out) + "\n"
    return pad + _emit_scalar(obj) + "\n"


def _emit_scalar(value) -> str:
    if value is None:
        return "~"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "" or text != text.strip() or any(
            ch in text for ch in ":#{}[],&*!|>'\"%@`") or text.lower() in (
            "true", "false", "null", "yes", "no", "~"):
        return '"' + text.replace('"', '\\"') + '"'
    return text
