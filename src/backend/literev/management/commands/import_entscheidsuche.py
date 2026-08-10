"""Import Swiss court decisions from entscheidsuche.ch into an ES index.

Scrolls the public entscheidsuche Elasticsearch backend for a given court
(default the Federal Court, ``CH_BGer``), maps each hit into the app's document
schema (see ``literev.libs.entscheidsuche.map_hit``) and indexes it into the
target index this app searches — making federal decisions available to the
normal search / cluster / RAG pipeline.

Courts are selected by their ``hierarchy`` code and the decision language by
``attachment.language`` (the current entscheidsuche schema).

Examples
--------
Preview 5 French Federal Court decisions without writing anything::

    python manage.py import_entscheidsuche --language fr --limit 5 --dry-run

Import all French Federal Court decisions into the ``bundesgericht`` index::

    python manage.py import_entscheidsuche --spider CH_BGer \
        --index bundesgericht --language fr

The target index name must match a source registered in
``literev.libs.search.SEARCH_SOURCE_OPTIONS`` for it to appear in the UI.

``--insecure`` skips TLS verification for the source connection; the public
entscheidsuche endpoint currently serves a certificate without its intermediate,
which ``requests`` cannot verify. The data is public, so skipping verification
for the read-only pull is acceptable.
"""

from __future__ import annotations

import json
import logging

from typing import Any

import requests

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser

from literev.libs.entscheidsuche import (
    FEDERAL_SPIDERS,
    SUPPORTED_LANGUAGES,
    map_hit,
)

logger = logging.getLogger(__name__)

DEFAULT_SOURCE_URL = "https://entscheidsuche.pansoft.de:9200"
DEFAULT_SPIDER = "CH_BGer"
_SCROLL_TTL = "2m"


class Command(BaseCommand):
    help = (
        "Import decisions from entscheidsuche.ch into an Elasticsearch index."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--spider",
            default=DEFAULT_SPIDER,
            help=(
                "entscheidsuche court code (hierarchy[1]) to import "
                f"(default {DEFAULT_SPIDER}; federal: "
                f"{', '.join(FEDERAL_SPIDERS)})."
            ),
        )
        parser.add_argument(
            "--index",
            default="bundesgericht",
            help="Target ES index / source key to write into.",
        )
        parser.add_argument(
            "--language",
            default="all",
            choices=("all", *SUPPORTED_LANGUAGES),
            help="Restrict to a single language (de/fr/it) or 'all'.",
        )
        parser.add_argument(
            "--from-date",
            default=None,
            help="Only import decisions on/after this ISO date (YYYY-MM-DD).",
        )
        parser.add_argument(
            "--batch-size", type=int, default=200, help="Scroll batch size."
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Stop after N mapped documents (0 = no limit).",
        )
        parser.add_argument(
            "--source-url",
            default=DEFAULT_SOURCE_URL,
            help="entscheidsuche Elasticsearch base URL.",
        )
        parser.add_argument(
            "--insecure",
            action="store_true",
            help="Skip TLS verification for the source (public data).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Map and print documents without indexing them.",
        )

    # -- source query ----------------------------------------------------

    def _build_query(
        self, spider: str, language: str, from_date: str | None
    ) -> dict[str, Any]:
        filters: list[dict[str, Any]] = [{"term": {"hierarchy": spider}}]
        if language != "all":
            filters.append({"term": {"attachment.language": language}})
        if from_date:
            filters.append({"range": {"date": {"gte": from_date}}})
        return {"query": {"bool": {"filter": filters}}}

    def _iter_source_hits(
        self,
        source_url: str,
        query: dict[str, Any],
        batch_size: int,
        verify: bool,
    ) -> Any:
        """Yield ``_source`` dicts from the entscheidsuche scroll API."""
        base = source_url.rstrip("/")
        body = {"size": batch_size, **query}
        response = requests.post(
            f"{base}/_all/_search?scroll={_SCROLL_TTL}",
            json=body,
            timeout=120,
            verify=verify,
        )
        response.raise_for_status()
        payload = response.json()
        scroll_id = payload.get("_scroll_id")

        while True:
            hits = payload.get("hits", {}).get("hits", [])
            if not hits:
                break
            for hit in hits:
                source = hit.get("_source")
                if isinstance(source, dict):
                    yield source
            if not scroll_id:
                break
            response = requests.post(
                f"{base}/_search/scroll",
                json={"scroll": _SCROLL_TTL, "scroll_id": scroll_id},
                timeout=120,
                verify=verify,
            )
            response.raise_for_status()
            payload = response.json()
            scroll_id = payload.get("_scroll_id")

    # -- destination -----------------------------------------------------

    def _destination_client(self) -> Any:
        from elasticsearch import Elasticsearch

        return Elasticsearch(
            [getattr(settings, "ES_HOST_URL", "")],
            basic_auth=(
                getattr(settings, "ES_USERNAME", ""),
                getattr(settings, "ES_PASSWORD", ""),
            ),
            verify_certs=bool(getattr(settings, "ES_SSL_CERTS", False)),
        )

    # -- entry point -----------------------------------------------------

    def handle(self, *args: Any, **options: Any) -> None:
        spider: str = options["spider"]
        index: str = options["index"]
        language: str = options["language"]
        from_date: str | None = options["from_date"]
        batch_size: int = options["batch_size"]
        limit: int = options["limit"]
        source_url: str = options["source_url"]
        verify: bool = not options["insecure"]
        dry_run: bool = options["dry_run"]

        query = self._build_query(spider, language, from_date)
        client = None if dry_run else self._destination_client()

        mapped = 0
        skipped = 0
        for source in self._iter_source_hits(
            source_url, query, batch_size, verify
        ):
            document = map_hit(source, collector_name=index)
            if document is None:
                skipped += 1
                continue

            if dry_run:
                if mapped < 3:
                    self.stdout.write(
                        json.dumps(document, ensure_ascii=False, indent=2)
                    )
            elif client is not None:
                client.index(
                    index=index,
                    id=document["record_key"],
                    document=document,
                )

            mapped += 1
            if mapped % 200 == 0:
                logger.info("Imported %s documents…", mapped)
            if limit and mapped >= limit:
                break

        verb = "Would import" if dry_run else "Imported"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {mapped} documents into '{index}' "
                f"(skipped {skipped} without text/signature)."
            )
        )
