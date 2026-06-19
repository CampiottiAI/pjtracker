"""In-memory LRU cache for parse results keyed by file content hash."""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from typing import Callable, TypeVar

T = TypeVar("T")

_MAX_ENTRIES = 16
_cache: OrderedDict[str, object] = OrderedDict()


def _content_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def cached_parse(
    file_bytes: bytes,
    cache_key: str,
    parser: Callable[[], T],
) -> T:
    """Return cached parse result or compute, store, and return."""
    key = f"{cache_key}:{_content_hash(file_bytes)}"
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]  # type: ignore[return-value]

    result = parser()
    _cache[key] = result
    while len(_cache) > _MAX_ENTRIES:
        _cache.popitem(last=False)
    return result


def clear_parse_cache() -> None:
    """Clear all cached parse results (mainly for tests)."""
    _cache.clear()
