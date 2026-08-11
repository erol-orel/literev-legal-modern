"""Tests for the opt-in document response cache (``libs.response_cache``).

``make_key`` is pure. ``get_or_set_payload`` is exercised against a real
in-memory cache (overriding the ``documents`` alias to LocMemCache) to lock in
the two behaviours that matter: payloads are cached and reused, and ``None``
(a 404 / no-access) is never cached, so access is always re-evaluated.
"""

from __future__ import annotations

from django.core.cache import caches
from django.test import SimpleTestCase, override_settings

from literev.libs.response_cache import get_or_set_payload, make_key

_LOCMEM = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "documents": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "response-cache-test",
    },
}


class MakeKeyTests(SimpleTestCase):
    def test_key_is_per_user_and_versioned(self) -> None:
        self.assertEqual(
            make_key("doc-content", 7, 42), "doc-content:v1:u7:42"
        )

    def test_different_users_get_different_keys(self) -> None:
        self.assertNotEqual(
            make_key("doc-content", 1, 42),
            make_key("doc-content", 2, 42),
        )


@override_settings(CACHES=_LOCMEM)
class GetOrSetPayloadTests(SimpleTestCase):
    def setUp(self) -> None:
        caches["documents"].clear()

    def test_caches_and_reuses_the_payload(self) -> None:
        calls: list[int] = []

        def producer() -> dict[str, int]:
            calls.append(1)
            return {"value": 1}

        key = make_key("t", 1, 1)
        self.assertEqual(get_or_set_payload(key, producer), {"value": 1})
        self.assertEqual(get_or_set_payload(key, producer), {"value": 1})
        self.assertEqual(len(calls), 1)  # producer ran only once

    def test_none_is_never_cached(self) -> None:
        calls: list[int] = []

        def producer() -> None:
            calls.append(1)
            return None

        key = make_key("t", 1, 2)
        self.assertIsNone(get_or_set_payload(key, producer))
        self.assertIsNone(get_or_set_payload(key, producer))
        self.assertEqual(len(calls), 2)  # recomputed each time
