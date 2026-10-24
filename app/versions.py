"""Version comparison helpers.

Conda and PyPI have different, fairly elaborate version ordering rules.  The
GUI only needs to answer "does the source advertise a version newer than the
installed one", so this module implements a pragmatic superset of the common
PEP 440 / conda patterns.  Exact equality is always detected; when a version is
too exotic to parse, a deterministic natural-sort comparison is used instead.
"""

from __future__ import annotations

import re
from functools import cmp_to_key
from typing import List, Optional, Tuple

_RELEASE_RE = re.compile(r"^\d+(?:\.\d+)*")
_MARKER_RE = re.compile(
    r"(?i)(?<![a-z])(dev|alpha|a|beta|b|rc|c|pre|post|rev|r)(\d*)"
)
_NATURAL_RE = re.compile(r"\d+|[a-z]+", re.IGNORECASE)

_PRE_RANK = {
    "dev": -4,
    "a": -3,
    "alpha": -3,
    "b": -2,
    "beta": -2,
    "c": -1,
    "rc": -1,
    "pre": -1,
}
_POST_RANK = {
    "post": 1,
    "rev": 1,
    "r": 1,
}

_RELEASE_RANK = 0


def _parse_version(value: str) -> Optional[Tuple[int, Tuple[int, ...], int, int, int]]:
    """Return a comparison tuple, or ``None`` for an unusual version."""

    raw = (value or "").strip()
    if not raw:
        return None

    # Public versions only; local labels do not change precedence.
    raw = raw.split("+", 1)[0]
    epoch = 0
    if "!" in raw:
        epoch_text, raw = raw.split("!", 1)
        try:
            epoch = int(epoch_text)
        except ValueError:
            epoch = 0

    core = raw.strip().lstrip("vV")
    core = core.replace("_", ".")
    if not core:
        return None

    match = _RELEASE_RE.match(core)
    if not match:
        return None

    release_text = match.group(0)
    release = tuple(int(part) for part in release_text.split("."))
    suffix = core[len(release_text) :].strip(" .-_")

    pre_rank = _RELEASE_RANK
    pre_number = 0
    post_rank = 0
    post_number = 0

    if suffix:
        marker_match = _MARKER_RE.search(suffix)
        if marker_match:
            marker = marker_match.group(1).lower()
            number_text = marker_match.group(2) or "0"
            try:
                number = int(number_text)
            except ValueError:
                number = 0
            # Leading text before a marker is not a normal PEP 440 suffix.
            # Let the natural comparison handle it.
            if marker_match.start() not in (0, 1):
                return None
            if marker in _PRE_RANK:
                pre_rank = _PRE_RANK[marker]
                pre_number = number
            elif marker in _POST_RANK:
                post_rank = _POST_RANK[marker]
                post_number = number
            else:
                return None
        elif suffix.isdigit():
            # Conda occasionally uses a numeric trailing segment as a build
            # counter (e.g. ``1.0.0_1``).  Treat it as an additional release
            # component for ordering purposes.
            release = release + (int(suffix),)
        elif re.fullmatch(r"[.\-]?\d+(?:[.\-]\d+)*", suffix):
            release = release + tuple(
                int(part) for part in re.findall(r"\d+", suffix)
            )
        else:
            return None

    return (epoch, release, pre_rank, pre_number, post_rank, post_number)


def _pad_release(left: Tuple[int, ...], right: Tuple[int, ...]) -> Tuple[Tuple[int, ...], Tuple[int, ...]]:
    length = max(len(left), len(right))
    return (
        left + (0,) * (length - len(left)),
        right + (0,) * (length - len(right)),
    )


def _natural_tokens(value: str) -> List[Tuple[int, object]]:
    tokens: List[Tuple[int, object]] = []
    for token in _NATURAL_RE.findall(value):
        if token.isdigit():
            tokens.append((1, int(token)))
        else:
            tokens.append((0, token.lower()))
    return tokens


def _compare_natural(left: str, right: str) -> int:
    left_tokens = _natural_tokens(left)
    right_tokens = _natural_tokens(right)
    length = max(len(left_tokens), len(right_tokens))
    for index in range(length):
        if index >= len(left_tokens):
            return -1
        if index >= len(right_tokens):
            return 1
        left_kind, left_value = left_tokens[index]
        right_kind, right_value = right_tokens[index]
        if left_kind != right_kind:
            # Numeric components sort after textual components.
            return -1 if left_kind < right_kind else 1
        if left_value != right_value:
            return -1 if left_value < right_value else 1
    return 0


def compare_versions(left: str, right: str) -> int:
    """Compare two version strings.

    Returns ``-1`` when *left* is older, ``0`` when equal, and ``1`` when
    *left* is newer.
    """

    left = (left or "").strip()
    right = (right or "").strip()
    if left == right:
        return 0
    if not left and not right:
        return 0
    if not left:
        return -1
    if not right:
        return 1

    parsed_left = _parse_version(left)
    parsed_right = _parse_version(right)
    if parsed_left is None or parsed_right is None:
        return _compare_natural(left, right)

    epoch_l, release_l, pre_rank_l, pre_num_l, post_rank_l, post_num_l = parsed_left
    epoch_r, release_r, pre_rank_r, pre_num_r, post_rank_r, post_num_r = parsed_right

    if epoch_l != epoch_r:
        return -1 if epoch_l < epoch_r else 1

    release_l, release_r = _pad_release(release_l, release_r)
    if release_l != release_r:
        return -1 if release_l < release_r else 1

    if pre_rank_l != pre_rank_r:
        return -1 if pre_rank_l < pre_rank_r else 1
    if pre_num_l != pre_num_r:
        return -1 if pre_num_l < pre_num_r else 1

    if post_rank_l != post_rank_r:
        return -1 if post_rank_l < post_rank_r else 1
    if post_num_l != post_num_r:
        return -1 if post_num_l < post_num_r else 1

    # Same public version, different local label / formatting.
    return 0


def is_newer(candidate: str, installed: str) -> bool:
    return compare_versions(candidate, installed) > 0


version_sort_key = cmp_to_key(compare_versions)
