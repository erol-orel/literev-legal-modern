"""Report which sources drive the section-based RAG pipeline.

A source uses the high-quality section pipeline (structured multi-section
answers + rich table summary) only when its section-embedded Chroma collection
exists and is non-empty; otherwise it silently falls back to the generic
pipeline (thinner answers/summaries). This command makes that state visible so
a "the answers look worse than production" report can be diagnosed at a glance.

    python manage.py rag_section_status
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from literev.libs.chroma_utils import (
    CHAMBER_COLLECTION_FALLBACKS,
    chroma_client,
    get_chamber_collection,
    has_section_collection,
)
from literev.libs.search import SECTION_SOURCES


class Command(BaseCommand):
    help = (
        "Show which sources have a usable section-embedded Chroma collection "
        "(section RAG) versus falling back to the generic RAG pipeline."
    )

    def handle(self, *args: object, **options: object) -> None:
        try:
            present = sorted(c.name for c in chroma_client.list_collections())
        except Exception as exc:  # pragma: no cover - depends on chroma state
            present = []
            self.stdout.write(
                self.style.ERROR(f"list_collections failed: {exc!r}")
            )
        self.stdout.write(f"Chroma collections present: {present}")
        self.stdout.write("")

        degraded_chambers = []
        for source in sorted(SECTION_SOURCES):
            usable = has_section_collection(source)
            try:
                count: object = get_chamber_collection(
                    chroma_client, source
                ).count()
            except Exception as exc:
                count = f"n/a ({type(exc).__name__})"

            pipeline = "SECTION (full)" if usable else "generic (fallback)"
            line = f"  {source:26} count={count!s:>10}  -> {pipeline}"
            if usable:
                self.stdout.write(self.style.SUCCESS(line))
            else:
                self.stdout.write(self.style.WARNING(line))
                if source in CHAMBER_COLLECTION_FALLBACKS:
                    degraded_chambers.append(source)

        self.stdout.write("")
        if degraded_chambers:
            self.stdout.write(
                self.style.ERROR(
                    "Geneva chambers on the generic fallback (thinner answers): "
                    + ", ".join(degraded_chambers)
                    + ". Deploy their section Chroma collections to restore "
                    "production-quality answers."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "All Geneva chambers use the full section pipeline."
                )
            )
