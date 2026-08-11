"""A small, opt-in response cache for immutable document payloads.

Fetching and rendering a decision's full HTML/text is one of the more
expensive read paths, and a decision's content never changes — an ideal cache
target. This helper wraps Django's ``documents`` cache alias (see
``settings.CACHES``), which is a **DummyCache no-op unless
``RESPONSE_CACHE_ENABLED``** is set, so importing and calling this changes
nothing until an operator turns it on and points the alias at Redis.

Cache keys are always scoped to the requesting user, so serving from cache can
never bypass the access checks the payload builders already perform.
"""

from __future__ import annotations

from typing import Any, Callable

from django.core.cache import caches

_CACHE_ALIAS = "documents"
_KEY_VERSION = "v1"


def make_key(prefix: str, user_id: int | str, ident: int | str) -> str:
    """A per-user, versioned cache key (bump ``_KEY_VERSION`` to invalidate)."""
    return f"{prefix}:{_KEY_VERSION}:u{user_id}:{ident}"


def get_or_set_payload(
    key: str,
    producer: Callable[[], Any],
    timeout: int | None = None,
) -> Any:
    """Return the cached payload for ``key`` or compute, store and return it.

    ``None`` results (a 404 / no-access) are never cached, so access decisions
    are always re-evaluated. With the cache disabled (DummyCache) this is just
    ``producer()`` — identical to no caching.
    """
    cache = caches[_CACHE_ALIAS]
    cached = cache.get(key)
    if cached is not None:
        return cached
    value = producer()
    if value is not None:
        cache.set(key, value, timeout)
    return value
