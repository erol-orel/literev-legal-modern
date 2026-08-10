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

Documents are written with the Elasticsearch ``_bulk`` helper (``--bulk-size``
per request, default 500), so a full ~110k-decision backfill completes in
minutes rather than the hour a per-document loop would take. Each document is
indexed under its ``record_key``, so a re-run overwrites rather than duplicates.

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

from typing import Any, Iterable, Iterator

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
_DEFAULT_BULK_SIZE = 500


def bulk_actions(
    index: str, documents: Iterable[dict[str, Any]]
) -> Iterator[dict[str, Any]]:
    """Yield Elasticsearch bulk actions for the mapped ``documents``.

    Each action indexes a document under its ``record_key`` so re-running the
    import overwrites rather than duplicates. Pure and unit-tested.
    """
    for document in documents:
        yield {
            "_index": index,
            "_id": document["record_key"],
            "_source": document,
        }


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
            "--bulk-size",
            type=int,
            default=_DEFAULT_BULK_SIZE,
            help="Documents per Elasticsearch _bulk request.",
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

    def _bulk_index(
        self,
        index: str,
        documents: Iterator[dict[str, Any]],
        bulk_size: int,
    ) -> int:
        """Index ``documents`` via the ES ``_bulk`` helper in chunks.

        Returns the number of successfully indexed documents. Individual failed
        actions are logged rather than aborting the whole run.
        """
        from elasticsearch.helpers import streaming_bulk

        client = self._destination_client()
        indexed = 0
        failed = 0
        for ok, item in streaming_bulk(
            client,
            bulk_actions(index, documents),
            chunk_size=bulk_size,
            raise_on_error=False,
            max_retries=3,
            initial_backoff=2,
            request_timeout=120,
        ):
            if ok:
                indexed += 1
                if indexed % 1000 == 0:
                    logger.info("Indexed %s documents…", indexed)
            else:
                failed += 1
                logger.warning("Bulk index action failed: %s", item)
        if failed:
            logger.warning(
                "Bulk index finished with %s failed actions.", failed
            )
        return indexed

    # -- entry point -----------------------------------------------------

    def handle(self, *args: Any, **options: Any) -> None:
        spider: str = options["spider"]
        index: str = options["index"]
        language: str = options["language"]
        from_date: str | None = options["from_date"]
        batch_size: int = options["batch_size"]
        bulk_size: int = options["bulk_size"]
        limit: int = options["limit"]
        source_url: str = options["source_url"]
        verify: bool = not options["insecure"]
        dry_run: bool = options["dry_run"]

        query = self._build_query(spider, language, from_date)
        stats = {"mapped": 0, "skipped": 0}

        def _mapped_documents() -> Iterator[dict[str, Any]]:
            for source in self._iter_source_hits(
                source_url, query, batch_size, verify
            ):
                document = map_hit(source, collector_name=index)
                if document is None:
                    stats["skipped"] += 1
                    continue
                if dry_run and stats["mapped"] < 3:
                    self.stdout.write(
                        json.dumps(document, ensure_ascii=False, indent=2)
                    )
                stats["mapped"] += 1
                yield document
                if limit and stats["mapped"] >= limit:
                    break

        if dry_run:
            # Consume the generator to drive mapping, counting and previews.
            for _ in _mapped_documents():
                pass
        else:
            self._bulk_index(index, _mapped_documents(), bulk_size)

        verb = "Would import" if dry_run else "Imported"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {stats['mapped']} documents into '{index}' "
                f"(skipped {stats['skipped']} without text/signature)."
            )
        )
