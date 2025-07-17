"""
Benchmark faithfulness scores of stored RAG answers with one or more LLMs
and report per-document latency.

Example
-------
python manage.py faithfulness_benchmark \
    --project 109 --rag 611 \
    --models openai mistral-24b phi3 \
    [--threshold 0.8] [--json]
"""

from __future__ import annotations

import asyncio
import json
import statistics
import time

from typing import Any, Dict, List, Sequence, Tuple

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import QuerySet

from literev.libs.scoring import (
    Faithfulness,
    HactarFaithfulnessLLM,
    SingleTurnSample,
)
from literev.models import Project, ProjectDocumentRAG, ProjectRAG

# Alias → provider / concrete-model mapping
MODEL_MAP: Dict[str, Dict[str, str]] = {
    "gpt-4o-mini": {"provider": "openai", "model": "gpt-4o-mini"},
    "phi3": {"provider": "hactar", "model": "phi3:14b"},
    "mistral-24b": {"provider": "hactar", "model": "mistral-small3.1:24b"},
}

INVALID_ANSWERS = {
    "",
    "réponse non disponible",
    "no content available.",
    "error generating response.",
}


# Helper functions
def _parse_models(raw: Sequence[str]) -> List[str]:
    """
    Accept space-separated aliases OR a single JSON array string.
    """
    if len(raw) == 1 and raw[0].lstrip().startswith("["):
        try:
            parsed = json.loads(raw[0])
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except json.JSONDecodeError as exc:
            raise CommandError(f"--models JSON parse error: {exc}") from exc
    return list(raw)


async def _timed_score(
    provider: str,
    model: str,
    query: str,
    answer: str,
    context: List[str],
) -> Tuple[float, float]:
    """
    Return (score, time_spent_s) for a single document.
    """
    api_key, base_url = (
        (settings.HACTAR_API_KEY, "https://hactar.unige.ch/api")
        if provider == "hactar"
        else (settings.OPENAI_API_KEY, "https://api.openai.com/v1")
    )

    llm = HactarFaithfulnessLLM(
        api_key=api_key, base_url=base_url, model=model
    )
    scorer = Faithfulness(llm=llm)

    sample = SingleTurnSample(
        user_input=query, response=answer, retrieved_contexts=context
    )

    t0 = time.perf_counter()
    score = await scorer.single_turn_ascore(sample)
    elapsed = round(time.perf_counter() - t0, 3)
    return score, elapsed


def _aggregate(
    scores: List[float], total_wall: float, thr: float
) -> Dict[str, Any]:
    """
    Compute global statistics.
    """
    return {
        "mean_score": round(statistics.mean(scores), 4),
        "median_score": round(statistics.median(scores), 4),
        "std_score": round(statistics.stdev(scores), 4)
        if len(scores) > 1
        else 0.0,
        "pct_ge_0_8": round(
            sum(s >= thr for s in scores) / len(scores) * 100, 2
        ),
        "total_time_s": round(total_wall, 3),
    }


# Management command
class Command(BaseCommand):
    help = "Benchmark faithfulness scores (per-document `time_spent_s`)."

    # -------------------------- CLI ------------------------------------- #
    def add_arguments(self, parser) -> None:
        parser.add_argument("--project", type=int, required=True)
        parser.add_argument("--rag", type=int, required=True)
        parser.add_argument(
            "--models",
            nargs="+",
            default=["openai", "mistral-24b", "phi3"],
            help="Space-separated aliases (openai, phi3, …) or one JSON array.",
        )
        parser.add_argument("--threshold", type=float, default=0.8)
        parser.add_argument("--json", action="store_true")

    # -------------------------- main ------------------------------------ #
    def handle(self, *args, **opts):
        project_id: int = opts["project"]
        rag_id: int = opts["rag"]
        thr: float = opts["threshold"]
        as_json: bool = opts["json"]

        aliases = _parse_models(opts["models"])
        unknown = [a for a in aliases if a not in MODEL_MAP]
        if unknown:
            raise CommandError(
                f"Unknown model alias(es): {', '.join(unknown)}. "
                f"Known aliases: {', '.join(MODEL_MAP)}"
            )

        # Validate DB objects
        project = Project.objects.filter(id=project_id).first()
        if not project:
            raise CommandError(f"Project {project_id} not found.")
        project_rag = ProjectRAG.objects.filter(
            id=rag_id, project=project
        ).first()
        if not project_rag:
            raise CommandError(
                f"ProjectRAG {rag_id} not linked to project {project_id}."
            )

        docs_qs: QuerySet[ProjectDocumentRAG] = (
            ProjectDocumentRAG.objects.filter(project_rag=project_rag)
            .exclude(answer__in=INVALID_ANSWERS)
            .only("document_id", "answer", "citation", "citation_context")
        )
        if not docs_qs:
            raise CommandError("No valid answers found for this RAG.")

        docs = [
            {
                "document_id": d.document_id,
                "answer": d.answer.strip(),
                "context": d.citation_context or [d.citation],
            }
            for d in docs_qs
        ]

        output: Dict[str, Any] = {"project_rag_id": rag_id, "models": {}}

        # For each requested model alias
        for alias in aliases:
            provider = MODEL_MAP[alias]["provider"]
            model_name = MODEL_MAP[alias]["model"]

            wall_start = time.perf_counter()
            coros = [
                _timed_score(
                    provider,
                    model_name,
                    project_rag.query,
                    d["answer"],
                    d["context"],
                )
                for d in docs
            ]
            scores_times = asyncio.get_event_loop().run_until_complete(
                asyncio.gather(*coros)
            )
            wall_total = time.perf_counter() - wall_start

            scores = [st[0] for st in scores_times]
            times = [st[1] for st in scores_times]

            documents: List[Dict[str, Any]] = []
            for idx in range(len(docs)):
                documents.append(
                    {
                        "document_id": docs[idx]["document_id"],
                        "score": round(scores[idx], 3),
                        "time_spent_s": times[idx],  # non-cumulative
                        "query": project_rag.query,
                        "answer": docs[idx]["answer"],
                        "context": docs[idx]["context"],
                    }
                )

            output["models"][alias] = {
                "provider": provider,
                "model_name": model_name,
                "metrics": _aggregate(scores, wall_total, thr),
                "documents": documents,
            }

        dump = json.dumps(
            output, ensure_ascii=False, indent=None if as_json else 2
        )
        self.stdout.write(dump)
