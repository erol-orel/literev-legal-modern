"""Embed section chunks into Elasticsearch — the Chroma → ES migration bridge.

Reads each source's existing section chunks (from its Chroma collection),
re-embeds the text through the free **Hactar** tier into a single vector space,
and bulk-indexes ``text`` + ``section_vector`` into one Elasticsearch section
index per source (``<source>_sections``). After this runs, the same store that
serves BM25 also serves dense kNN, so retrieval can move onto the ES hybrid
(RRF) path and the separate Chroma store can be retired.

It is the read-side counterpart to :mod:`lr_search.hybrid`/:mod:`lr_search.indexing`
(the query and document builders, which are pure and unit-tested). This command
is the thin I/O orchestration that only runs on the VM, where Chroma, Hactar and
Elasticsearch are reachable. It is **idempotent**: stable per-chunk ids mean a
re-run overwrites in place, and ``--recreate`` rebuilds an index from scratch.

Examples
--------
Migrate the Geneva civil chamber, recreating its index::

    python manage.py embed_sections_to_es --source chambre_civile --recreate

All section sources, capped for a first look::

    python manage.py embed_sections_to_es --limit 2000

Preview what would be indexed without writing::

    python manage.py embed_sections_to_es --source bundesgericht --dry-run
"""

from __future__ import annotations

from typing import Any, Iterator

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser

from lr_search import (
    iter_batches,
    iter_section_bulk_actions,
    section_document,
    section_index_mapping,
    section_index_name,
)

# Chroma page size for reading chunks; ES batch size for embed + bulk write.
CHROMA_PAGE = 1000
DEFAULT_BATCH = 128


class Command(BaseCommand):
    help = "Embed section chunks (via Hactar) into an Elasticsearch index."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--source",
            default="",
            help=(
                "Comma-separated source key(s) to migrate "
                "(default: all section sources)."
            ),
        )
        parser.add_argument(
            "--engine",
            default="hactar",
            help="Embedding engine: 'hactar' (free, default) or 'openai'.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH,
            help=f"Embed/bulk batch size (default: {DEFAULT_BATCH}).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Max chunks per source (0 = all).",
        )
        parser.add_argument(
            "--recreate",
            action="store_true",
            help="Drop and recreate the section index before indexing.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Read and count chunks but do not embed or write to ES.",
        )

    # -- Elasticsearch -----------------------------------------------------
    def _client(self) -> Any:
        from elasticsearch import Elasticsearch

        return Elasticsearch(
            [getattr(settings, "ES_HOST_URL", "")],
            basic_auth=(
                getattr(settings, "ES_USERNAME", ""),
                getattr(settings, "ES_PASSWORD", ""),
            ),
            verify_certs=bool(getattr(settings, "ES_SSL_CERTS", False)),
        )

    def _ensure_index(
        self, client: Any, index: str, dims: int, recreate: bool
    ) -> None:
        if recreate and client.indices.exists(index=index):
            client.indices.delete(index=index)
            self.stdout.write(f"  dropped existing index {index}")
        if not client.indices.exists(index=index):
            client.indices.create(index=index, **section_index_mapping(dims))
            self.stdout.write(f"  created index {index} (dims={dims})")

    # -- Chroma source -----------------------------------------------------
    def _iter_chunks(
        self, source: str, limit: int
    ) -> Iterator[dict[str, Any]]:
        """Yield ``{record_key, section, text, decision_date}`` per chunk."""
        from literev.libs.chroma_utils import (
            chroma_client,
            get_chamber_collection,
        )

        collection = get_chamber_collection(chroma_client, source)
        offset = 0
        emitted = 0
        while True:
            page = collection.get(
                include=["documents", "metadatas"],
                limit=CHROMA_PAGE,
                offset=offset,
            )
            documents = page.get("documents") or []
            metadatas = page.get("metadatas") or []
            if not documents:
                break
            for text, meta in zip(documents, metadatas):
                meta = meta or {}
                record_key = str(meta.get("record_key") or "")
                if not record_key or not str(text or "").strip():
                    continue
                yield {
                    "record_key": record_key,
                    "section": str(meta.get("section") or ""),
                    "text": str(text),
                    "decision_date": (
                        str(meta.get("decision_date"))
                        if meta.get("decision_date")
                        else None
                    ),
                }
                emitted += 1
                if limit and emitted >= limit:
                    return
            offset += len(documents)

    # -- Orchestration -----------------------------------------------------
    def _sources(self, raw: str) -> list[str]:
        from literev.libs.search import SECTION_SOURCES

        if raw.strip():
            return [s.strip() for s in raw.split(",") if s.strip()]
        return sorted(SECTION_SOURCES)

    def _migrate_source(
        self,
        source: str,
        *,
        engine: str,
        batch_size: int,
        limit: int,
        recreate: bool,
        dry_run: bool,
    ) -> int:
        from elasticsearch.helpers import bulk

        from literev.libs.chroma_utils import embed_texts

        index = section_index_name(source)
        client = None if dry_run else self._client()
        index_ready = False
        written = 0

        for batch in iter_batches(
            self._iter_chunks(source, limit), batch_size
        ):
            if dry_run:
                written += len(batch)
                continue

            vectors = embed_texts([c["text"] for c in batch], engine)
            documents = [
                section_document(
                    record_key=chunk["record_key"],
                    source=source,
                    section=chunk["section"],
                    text=chunk["text"],
                    vector=vector,
                    decision_date=chunk["decision_date"],
                )
                for chunk, vector in zip(batch, vectors)
            ]
            if not index_ready:
                self._ensure_index(client, index, len(vectors[0]), recreate)
                index_ready = True
            success, _ = bulk(
                client, iter_section_bulk_actions(index, documents)
            )
            written += success

        return written

    def handle(self, *args: Any, **options: Any) -> None:
        engine = str(options["engine"])
        batch_size = int(options["batch_size"])
        limit = int(options["limit"])
        recreate = bool(options["recreate"])
        dry_run = bool(options["dry_run"])

        total = 0
        for source in self._sources(str(options["source"])):
            self.stdout.write(f"{source} → {section_index_name(source)}")
            try:
                count = self._migrate_source(
                    source,
                    engine=engine,
                    batch_size=batch_size,
                    limit=limit,
                    recreate=recreate,
                    dry_run=dry_run,
                )
            except Exception as exc:
                self.stderr.write(
                    self.style.WARNING(f"  skipped {source}: {exc}")
                )
                continue
            total += count
            verb = "would index" if dry_run else "indexed"
            self.stdout.write(self.style.SUCCESS(f"  {verb} {count} chunks"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {total} chunks across the selected sources."
            )
        )
