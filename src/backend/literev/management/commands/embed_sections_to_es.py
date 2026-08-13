"""Embed section chunks into Elasticsearch — the Chroma → ES migration bridge.

Reads each source's existing section chunks (by default straight from Chroma's
SQLite metadata segment, which never loads the memory-heavy HNSW index),
re-embeds the text with the configured engine (``settings.HYBRID_EMBED_ENGINE``,
OpenAI ``text-embedding-3-large`` for the Geneva sections) into a single vector
space, and bulk-indexes ``text`` + ``section_vector`` into one Elasticsearch
section index per source (``<source>_sections``). After this runs, the same
store that serves BM25 also serves dense kNN, so retrieval can move onto the ES
hybrid (RRF) path and the separate Chroma store can be retired.

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
    bulk_index_action,
    iter_batches,
    section_doc_id,
    section_document,
    section_index_mapping,
    section_index_name,
)

# Chroma page size for reading chunks; ES batch size for embed + bulk write.
CHROMA_PAGE = 1000
DEFAULT_BATCH = 128


class Command(BaseCommand):
    help = "Embed section chunks into an Elasticsearch section index."

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
            default="",
            help=(
                "Embedding engine: 'openai' or 'hactar'. Empty (default) uses "
                "settings.HYBRID_EMBED_ENGINE so the build matches the query "
                "side (OpenAI for the Geneva sections)."
            ),
        )
        parser.add_argument(
            "--reader",
            default="sqlite",
            choices=("sqlite", "chroma"),
            help=(
                "How to read section chunks. 'sqlite' (default) reads Chroma's "
                "SQLite metadata segment directly — never loads the HNSW index, "
                "so it works on large collections in low memory. 'chroma' uses "
                "the Chroma client (loads the index; OOMs on big collections)."
            ),
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
            "--skip-existing",
            action="store_true",
            help=(
                "Resume: skip chunks already present in the index (by stable "
                "id) and embed only the missing ones. Makes a re-run cheap and "
                "safe after an interruption (e.g. exhausted API credits). "
                "Never recreates the index; ignored on a not-yet-created one."
            ),
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

    def _iter_chunks_sqlite(
        self, source: str, limit: int
    ) -> Iterator[dict[str, Any]]:
        """Yield ``{record_key, section, text, decision_date}`` per chunk read
        straight from Chroma's SQLite metadata segment.

        Bypasses the Chroma client with a read-only ``sqlite3`` connection, so
        it never loads the HNSW vector index — the operation that exhausts
        memory on large collections (``chambre_administrative`` is >2M chunks).
        Streams one chunk at a time: rows come back ordered by embedding id, so
        we accumulate an embedding's metadata keys until the id changes, emit,
        and move on, never holding the corpus in memory.
        """
        import sqlite3

        from literev.libs.chroma_utils import (
            CHAMBER_COLLECTION_FALLBACKS,
            CHROMA_DIR,
        )

        db_path = f"{CHROMA_DIR}/chroma.sqlite3"
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:

            def _collection_id(name: str) -> str | None:
                if not name:
                    return None
                row = con.execute(
                    "SELECT id FROM collections WHERE name = ?", (name,)
                ).fetchone()
                return row[0] if row else None

            collection_id = _collection_id(source) or _collection_id(
                CHAMBER_COLLECTION_FALLBACKS.get(source, "")
            )
            if not collection_id:
                raise ValueError(
                    f"collection {source!r} not found in {db_path}"
                )
            segment = con.execute(
                "SELECT id FROM segments "
                "WHERE collection = ? AND scope = 'METADATA'",
                (collection_id,),
            ).fetchone()
            if not segment:
                raise ValueError(
                    f"no METADATA segment for collection {source!r}"
                )

            cursor = con.execute(
                "SELECT m.id, m.key, m.string_value "
                "FROM embedding_metadata m "
                "JOIN embeddings e ON e.id = m.id "
                "WHERE e.segment_id = ? "
                "ORDER BY m.id",
                (segment[0],),
            )

            def _build(fields: dict[str, str]) -> dict[str, Any] | None:
                text = (fields.get("chroma:document") or "").strip()
                record_key = (fields.get("record_key") or "").strip()
                if not text or not record_key:
                    return None
                return {
                    "record_key": record_key,
                    "section": fields.get("section") or "",
                    "text": text,
                    "decision_date": None,
                }

            emitted = 0
            current_id: int | None = None
            fields: dict[str, str] = {}
            for row_id, key, string_value in cursor:
                if current_id is not None and row_id != current_id:
                    chunk = _build(fields)
                    if chunk is not None:
                        yield chunk
                        emitted += 1
                        if limit and emitted >= limit:
                            return
                    fields = {}
                current_id = row_id
                if string_value is not None:
                    fields[key] = string_value
            if current_id is not None:
                chunk = _build(fields)
                if chunk is not None:
                    yield chunk
        finally:
            con.close()

    # -- Orchestration -----------------------------------------------------
    def _sources(self, raw: str) -> list[str]:
        from literev.libs.search import SECTION_SOURCES

        if raw.strip():
            return [s.strip() for s in raw.split(",") if s.strip()]
        return sorted(SECTION_SOURCES)

    @staticmethod
    def _with_ids(
        chunks: Iterator[dict[str, Any]],
    ) -> Iterator[dict[str, Any]]:
        """Annotate each chunk with its stable ``doc_id``.

        The ordinal is the running position of the chunk within its
        ``(record_key, section)`` group over the whole stream — identical to
        ``iter_section_bulk_actions`` — so the id matches what a previous run
        wrote. Deterministic because the SQLite reader yields chunks in a
        fixed order (``ORDER BY embedding id``), which is what makes
        ``--skip-existing`` correct across runs.
        """
        seen: dict[tuple[str, str], int] = {}
        for chunk in chunks:
            key = (chunk["record_key"], chunk["section"])
            ordinal = seen.get(key, 0)
            seen[key] = ordinal + 1
            chunk["doc_id"] = section_doc_id(
                chunk["record_key"], chunk["section"], ordinal
            )
            yield chunk

    def _existing_ids(
        self, client: Any, index: str, ids: list[str]
    ) -> set[str]:
        """Return which of ``ids`` already exist in ``index`` (via mget)."""
        resp = client.mget(index=index, ids=ids, _source=False)
        return {
            doc["_id"] for doc in resp.get("docs", []) if doc.get("found")
        }

    def _migrate_source(
        self,
        source: str,
        *,
        engine: str,
        reader: str,
        batch_size: int,
        limit: int,
        recreate: bool,
        skip_existing: bool,
        dry_run: bool,
    ) -> tuple[int, int]:
        from elasticsearch.helpers import bulk

        from literev.libs.chroma_utils import embed_texts

        index = section_index_name(source)
        # `Any` (not `Any | None`): the ES client is only touched on the
        # non-dry-run path, but mypy can't see the dry-run short-circuit.
        client: Any = None if dry_run else self._client()

        # --skip-existing resumes an *existing* index (never recreates); it is
        # a no-op if the index does not exist yet, in which case we fall back to
        # a normal fresh build.
        if skip_existing and not dry_run:
            if client.indices.exists(index=index):
                recreate = False
            else:
                skip_existing = False

        index_ready = False
        written = 0
        skipped = 0

        iter_chunks = (
            self._iter_chunks_sqlite
            if reader == "sqlite"
            else self._iter_chunks
        )
        stream = self._with_ids(iter_chunks(source, limit))
        for batch in iter_batches(stream, batch_size):
            if dry_run:
                written += len(batch)
                continue

            if skip_existing:
                present = self._existing_ids(
                    client, index, [c["doc_id"] for c in batch]
                )
                if present:
                    skipped += len(present)
                    batch = [c for c in batch if c["doc_id"] not in present]
                if not batch:
                    continue

            vectors = embed_texts([c["text"] for c in batch], engine)
            if not index_ready:
                self._ensure_index(client, index, len(vectors[0]), recreate)
                index_ready = True
            actions = [
                bulk_index_action(
                    index,
                    chunk["doc_id"],
                    section_document(
                        record_key=chunk["record_key"],
                        source=source,
                        section=chunk["section"],
                        text=chunk["text"],
                        vector=vector,
                        decision_date=chunk["decision_date"],
                    ),
                )
                for chunk, vector in zip(batch, vectors)
            ]
            success, _ = bulk(client, actions)
            written += success

        if skipped:
            self.stdout.write(f"  skipped {skipped} already-indexed chunks")
        return written, skipped

    def handle(self, *args: Any, **options: Any) -> None:
        engine = str(options["engine"]) or str(
            getattr(settings, "HYBRID_EMBED_ENGINE", "openai")
        )
        reader = str(options["reader"])
        batch_size = int(options["batch_size"])
        limit = int(options["limit"])
        recreate = bool(options["recreate"])
        skip_existing = bool(options["skip_existing"])
        dry_run = bool(options["dry_run"])

        total = 0
        for source in self._sources(str(options["source"])):
            self.stdout.write(
                f"{source} → {section_index_name(source)} "
                f"(engine={engine}, reader={reader}"
                f"{', skip-existing' if skip_existing else ''})"
            )
            try:
                count, _skipped = self._migrate_source(
                    source,
                    engine=engine,
                    reader=reader,
                    batch_size=batch_size,
                    limit=limit,
                    recreate=recreate,
                    skip_existing=skip_existing,
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
