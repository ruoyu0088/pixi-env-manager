"""A small, dependency-free TOML lexer used by the editor.

It is intentionally forgiving: the goal is pleasant syntax colouring while the
user is typing, not full validation.  ``tomllib`` is used separately when a
file is saved.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class Token:
    start: int
    end: int
    kind: str


_DATE_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}"
    r"(?:[Tt ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})?)?"
)
_TIME_RE = re.compile(r"\d{2}:\d{2}:\d{2}(?:\.\d+)?")
_NUMBER_RE = re.compile(
    r"[-+]?(?:"
    r"0[xX][0-9A-Fa-f_]+|"
    r"0[oO][0-7_]+|"
    r"0[bB][01_]+|"
    r"(?:\d[\d_]*)(?:\.\d[\d_]*)?(?:[eE][-+]?\d[\d_]*)?|"
    r"inf|nan"
    r")"
)
_INLINE_KEY_RE = re.compile(r"[A-Za-z0-9_-]+(?=\s*=)")
_TABLE_RE = re.compile(r"\[\[?[^\]]+\]\]?")


def _find_unquoted(text: str, start: int, end: int, target: str) -> int:
    index = start
    quote: Optional[str] = None
    while index < end:
        character = text[index]
        if quote:
            if quote == '"' and character == "\\":
                index += 2
                continue
            if character == quote:
                quote = None
            index += 1
            continue
        if character == "#":
            return -1
        if character in "\"'":
            quote = character
            index += 1
            continue
        if character == target:
            return index
        index += 1
    return -1


def _regular_string_end(text: str, start: int, end: int, quote: str) -> int:
    index = start + 1
    while index < end:
        character = text[index]
        if quote == '"' and character == "\\":
            index += 2
            continue
        if character == quote:
            return index + 1
        index += 1
    return end


def _scan_value(
    text: str,
    start: int,
    end: int,
    tokens: List[Token],
) -> Optional[str]:
    index = start
    while index < end:
        character = text[index]
        if character in " \t":
            index += 1
            continue
        if character == "#":
            tokens.append(Token(index, end, "comment"))
            return None
        if character in "\"'":
            quote = character
            triple = text[index : index + 3]
            if triple == quote * 3:
                close = text.find(quote * 3, index + 3)
                if close == -1 or close >= end:
                    tokens.append(Token(index, end, "string"))
                    return quote * 3
                tokens.append(Token(index, close + 3, "string"))
                index = close + 3
                continue
            close = _regular_string_end(text, index, end, quote)
            tokens.append(Token(index, close, "string"))
            index = close
            continue
        # Date/time must be checked before the generic number pattern.
        if character.isdigit():
            date_match = _DATE_RE.match(text, index, end)
            if date_match:
                tokens.append(Token(index, date_match.end(), "date"))
                index = date_match.end()
                continue
            time_match = _TIME_RE.match(text, index, end)
            if time_match:
                tokens.append(Token(index, time_match.end(), "date"))
                index = time_match.end()
                continue
        number_match = _NUMBER_RE.match(text, index, end)
        if number_match and number_match.end() > index:
            tokens.append(Token(index, number_match.end(), "number"))
            index = number_match.end()
            continue
        if text.startswith("true", index) and (
            index + 4 == end or not text[index + 4].isalnum()
        ):
            tokens.append(Token(index, index + 4, "boolean"))
            index += 4
            continue
        if text.startswith("false", index) and (
            index + 5 == end or not text[index + 5].isalnum()
        ):
            tokens.append(Token(index, index + 5, "boolean"))
            index += 5
            continue
        inline_key = _INLINE_KEY_RE.match(text, index, end)
        if inline_key:
            tokens.append(Token(index, inline_key.end(), "key"))
            index = inline_key.end()
            continue
        if character == "=":
            tokens.append(Token(index, index + 1, "operator"))
            index += 1
            continue
        if character in "[]{},":
            tokens.append(Token(index, index + 1, "punct"))
            index += 1
            continue
        index += 1
    return None


def tokenize(text: str) -> List[Token]:
    tokens: List[Token] = []
    multiline: Optional[str] = None
    length = len(text)
    line_start = 0

    while line_start <= length:
        line_end = text.find("\n", line_start)
        if line_end == -1:
            line_end = length
        index = line_start

        if multiline:
            close = text.find(multiline, line_start, line_end)
            if close == -1:
                if line_end > line_start:
                    tokens.append(Token(line_start, line_end, "string"))
                if line_end >= length:
                    break
                line_start = line_end + 1
                continue
            tokens.append(Token(line_start, close + 3, "string"))
            index = close + 3
            multiline = None

        # Leading comment.
        while index < line_end and text[index] in " \t":
            index += 1
        if index >= line_end:
            if line_end >= length:
                break
            line_start = line_end + 1
            continue
        if text[index] == "#":
            tokens.append(Token(index, line_end, "comment"))
            if line_end >= length:
                break
            line_start = line_end + 1
            continue

        # Table header.  A line starting with '[' but containing '=' is a
        # continuation of an array value, not a table header.
        if text[index] == "[" and _find_unquoted(text, index, line_end, "=") == -1:
            match = _TABLE_RE.match(text, index, line_end)
            if match and "," not in match.group(0):
                tokens.append(Token(match.start(), match.end(), "table"))
                after = match.end()
                comment = text.find("#", after, line_end)
                if comment != -1:
                    tokens.append(Token(comment, line_end, "comment"))
                if line_end >= length:
                    break
                line_start = line_end + 1
                continue

        equals = _find_unquoted(text, index, line_end, "=")
        if equals != -1:
            key_end = equals
            while key_end > index and text[key_end - 1] in " \t":
                key_end -= 1
            if key_end > index:
                tokens.append(Token(index, key_end, "key"))
            tokens.append(Token(equals, equals + 1, "operator"))
            new_state = _scan_value(text, equals + 1, line_end, tokens)
            if new_state:
                multiline = new_state
        else:
            new_state = _scan_value(text, index, line_end, tokens)
            if new_state:
                multiline = new_state

        if line_end >= length:
            break
        line_start = line_end + 1

    tokens.sort(key=lambda token: (token.start, token.end))
    return tokens


def tokens_by_kind(tokens: List[Token]) -> dict:
    grouped: dict = {}
    for token in tokens:
        grouped.setdefault(token.kind, []).append(token)
    return grouped
