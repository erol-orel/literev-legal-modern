"""Build a case-law citation graph over the Elasticsearch corpus.

Scrolls one or more search indices, extracts the Swiss federal citations
(``ATF``/``BGE``/``DTF`` and Federal Court docket numbers) from each decision's
text via ``lr_legal.build_citation_edges``, and writes a directed citation
graph as JSON: the edge list plus each node's in-degree (how often it is cited).

This is the foundation for surfacing **adverse and distinguishing authority**
and for flagging decisions that have been heavily cited (leading) — the feature
no generic RAG has. The extraction logic is pure and unit-tested in
``lr-legal``; this command only feeds the corpus through it, so it runs on the
VM where Elasticsearch holds the decisions.

Examples
--------
Build the graph for the Federal Court index, writing to a file::

    python manage.py build_citation_graph --index bundesgericht --output graph.json

Across several indices, capped for a first look::

    python manage.py build_citation_graph \
        --index chambre_administrative,chambre_penale --limit 5000
"""

from __future__ import annotations

import json

from collections import Counter
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser

from lr_legal import build_citation_edges

TEXT_FIELD = "raw_document_text"


class Command(BaseCommand):
    """Extract inter-decision citations from ES and emit a citation graph."""

    help = "Build a Swiss case-law citation graph from the ES corpus."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--index",
            required=True,
            help="Comma-separated ES index name(s) to scan.",
        )
        parser.add_argument(
            "--output",
            default="citation_graph.json",
            help="Path to write the graph JSON (default: citation_graph.json).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Max decisions to scan (0 = all).",
        )

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

    def _records(self, indices: str, limit: int) -> list[tuple[str, str]]:
        from elasticsearch.helpers import scan

        client = self._client()
        records: list[tuple[str, str]] = []
        for hit in scan(
            client,
            index=indices,
            query={"query": {"match_all": {}}},
            _source=[TEXT_FIELD],
        ):
            record_key = str(hit.get("_id") or "")
            text = str((hit.get("_source") or {}).get(TEXT_FIELD) or "")
            if record_key and text:
                records.append((record_key, text))
                if limit and len(records) >= limit:
                    break
        return records

    def handle(self, *args: Any, **options: Any) -> None:
        indices = options["index"]
        limit = int(options["limit"])

        self.stdout.write(f"Scanning {indices}…")
        records = self._records(indices, limit)
        self.stdout.write(f"Read {len(records)} decisions.")

        edges = build_citation_edges(records, with_treatment=True)
        in_degree = Counter(edge["target"] for edge in edges)
        # Decisions carrying incoming overruled/criticised edges — the
        # "verify: still good law?" set — with a count per target.
        negative = Counter(
            edge["target"]
            for edge in edges
            if edge.get("treatment") in ("overruled", "criticized")
        )
        graph = {
            "n_decisions": len(records),
            "n_edges": len(edges),
            "edges": edges,
            "in_degree": dict(in_degree.most_common()),
            "treated_negatively": dict(negative.most_common()),
        }

        with open(options["output"], "w", encoding="utf-8") as handle:
            json.dump(graph, handle, ensure_ascii=False, indent=2)

        top = in_degree.most_common(10)
        self.stdout.write(
            self.style.SUCCESS(
                f"Wrote {options['output']}: {len(edges)} edges over "
                f"{len(records)} decisions."
            )
        )
        if top:
            self.stdout.write("Most-cited decisions:")
            for key, count in top:
                self.stdout.write(f"  {count:>4}  {key}")
        if negative:
            self.stdout.write(
                self.style.WARNING(
                    "\nTreated negatively (verify — still good law?):"
                )
            )
            for key, count in negative.most_common(10):
                self.stdout.write(f"  {count:>4}  {key}")
