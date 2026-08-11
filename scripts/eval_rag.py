#!/usr/bin/env python3
"""Offline quality evaluation for the RAG answering pipeline.

In legal work a wrong answer is a liability, not a bug ticket — so every
change to retrieval, prompts or the model should be measured against a fixed
gold set before it ships. This standalone script (no Django, no app imports)
scores a run of the pipeline on three axes a jurist cares about:

  * **Verdict accuracy** — did the closed-question verdict (oui / non /
    peut-être / mixte) match the labelled answer?
  * **Citation precision / recall** — of the decisions the pipeline cited, how
    many were actually relevant, and of the relevant decisions, how many did it
    surface? (micro = pooled over all cases, macro = averaged per case).
  * **Faithfulness** — the mean Ragas grounding score, when present.

Inputs are two JSON files joined by a case ``id``:

``gold.json`` (the labels — write these once, by hand)::

    [
      {
        "id": "bail-resiliation-01",
        "question": "Le bailleur peut-il résilier le bail de manière anticipée ?",
        "expected_verdict": "oui",                 // optional
        "relevant_ids": ["ATA_123_2023", "ATA_98_2022"]  // optional
      }
    ]

``predictions.json`` (dumped from the pipeline / API for the same cases)::

    [
      {
        "id": "bail-resiliation-01",
        "verdict": "oui",                          // or omit and pass "counts"
        "counts": {"oui": 4, "non": 1, "peut_etre": 0, "mixte": 0},
        "cited_ids": ["ATA_123_2023", "ATA_55_2021"],
        "confidence_scores": [0.82, 0.71, 0.66]
      }
    ]

Everything is optional per case: a case with no ``expected_verdict`` is skipped
for verdict accuracy, one with no ``relevant_ids`` is skipped for citation
metrics, and so on — so a partial gold set still produces the metrics it can.

Usage::

    python scripts/eval_rag.py --gold gold.json --predictions predictions.json
    python scripts/eval_rag.py --gold g.json --predictions p.json --json out.json
"""

from __future__ import annotations

import argparse
import json
import statistics

from pathlib import Path
from typing import Any, Iterable, Sequence

VERDICTS = ("oui", "non", "peut_etre", "mixte")


def dominant_verdict(prediction: dict[str, Any]) -> str | None:
    """The predicted verdict: an explicit ``verdict`` or the argmax of counts."""
    explicit = prediction.get("verdict")
    if isinstance(explicit, str) and explicit:
        return explicit
    counts = prediction.get("counts")
    if isinstance(counts, dict) and counts:
        present = {k: counts.get(k, 0) or 0 for k in VERDICTS}
        if any(present.values()):
            return max(present, key=lambda k: present[k])
    return None


def prf(predicted: Sequence[str], relevant: Sequence[str]) -> dict[str, float]:
    """Precision / recall / F1 of a predicted set against a relevant set."""
    pred_set = {str(x) for x in predicted}
    rel_set = {str(x) for x in relevant}
    if not pred_set and not rel_set:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "tp": 0}
    tp = len(pred_set & rel_set)
    precision = tp / len(pred_set) if pred_set else 0.0
    recall = tp / len(rel_set) if rel_set else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0.0
    )
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp}


def _index_by_id(
    rows: Iterable[dict[str, Any]], label: str
) -> dict[str, dict]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        rid = row.get("id")
        if rid is None:
            raise ValueError(f"Every {label} entry needs an 'id'.")
        out[str(rid)] = row
    return out


def evaluate(
    gold: list[dict[str, Any]], predictions: list[dict[str, Any]]
) -> dict[str, Any]:
    """Join gold + predictions by id and compute the aggregate metrics."""
    preds = _index_by_id(predictions, "prediction")

    verdict_total = verdict_correct = 0
    faithfulness: list[float] = []
    macro_p: list[float] = []
    macro_r: list[float] = []
    macro_f: list[float] = []
    micro_tp = micro_pred = micro_rel = 0
    missing: list[str] = []

    for case in gold:
        cid = str(case.get("id"))
        prediction = preds.get(cid)
        if prediction is None:
            missing.append(cid)
            continue

        expected = case.get("expected_verdict")
        if isinstance(expected, str) and expected:
            verdict_total += 1
            if dominant_verdict(prediction) == expected:
                verdict_correct += 1

        if "relevant_ids" in case:
            relevant = case.get("relevant_ids") or []
            predicted = prediction.get("cited_ids") or []
            scores = prf(predicted, relevant)
            macro_p.append(scores["precision"])
            macro_r.append(scores["recall"])
            macro_f.append(scores["f1"])
            micro_tp += int(scores["tp"])
            micro_pred += len({str(x) for x in predicted})
            micro_rel += len({str(x) for x in relevant})

        for score in prediction.get("confidence_scores") or []:
            if isinstance(score, (int, float)):
                faithfulness.append(float(score))

    micro_precision = micro_tp / micro_pred if micro_pred else 0.0
    micro_recall = micro_tp / micro_rel if micro_rel else 0.0
    micro_f1 = (
        2 * micro_precision * micro_recall / (micro_precision + micro_recall)
        if (micro_precision + micro_recall)
        else 0.0
    )

    return {
        "n_gold": len(gold),
        "n_scored": len(gold) - len(missing),
        "missing_predictions": missing,
        "verdict": {
            "evaluated": verdict_total,
            "correct": verdict_correct,
            "accuracy": (
                verdict_correct / verdict_total if verdict_total else None
            ),
        },
        "citations": {
            "evaluated": len(macro_f),
            "micro": {
                "precision": micro_precision,
                "recall": micro_recall,
                "f1": micro_f1,
            },
            "macro": {
                "precision": statistics.mean(macro_p) if macro_p else None,
                "recall": statistics.mean(macro_r) if macro_r else None,
                "f1": statistics.mean(macro_f) if macro_f else None,
            },
        },
        "faithfulness": {
            "n": len(faithfulness),
            "mean": statistics.mean(faithfulness) if faithfulness else None,
        },
    }


def _fmt(value: float | None) -> str:
    return "  —  " if value is None else f"{value:.3f}"


def render(report: dict[str, Any]) -> str:
    """A compact, human-readable rendering of the metrics."""
    lines = [
        "",
        f"Cases        : {report['n_scored']}/{report['n_gold']} scored"
        + (
            f"  ({len(report['missing_predictions'])} missing predictions)"
            if report["missing_predictions"]
            else ""
        ),
        "",
        "Verdict accuracy:",
        f"  {report['verdict']['correct']}/{report['verdict']['evaluated']}"
        f"  = {_fmt(report['verdict']['accuracy'])}",
        "",
        f"Citations (over {report['citations']['evaluated']} cases):",
        f"  micro  P {_fmt(report['citations']['micro']['precision'])}"
        f"  R {_fmt(report['citations']['micro']['recall'])}"
        f"  F1 {_fmt(report['citations']['micro']['f1'])}",
        f"  macro  P {_fmt(report['citations']['macro']['precision'])}"
        f"  R {_fmt(report['citations']['macro']['recall'])}"
        f"  F1 {_fmt(report['citations']['macro']['f1'])}",
        "",
        f"Faithfulness : mean {_fmt(report['faithfulness']['mean'])}"
        f"  (n={report['faithfulness']['n']})",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument(
        "--json", type=Path, help="Also write the full metrics as JSON here"
    )
    args = parser.parse_args()

    gold = json.loads(args.gold.read_text(encoding="utf-8"))
    predictions = json.loads(args.predictions.read_text(encoding="utf-8"))
    if not isinstance(gold, list) or not isinstance(predictions, list):
        parser.error("Both files must contain a JSON list.")

    report = evaluate(gold, predictions)
    print(render(report))
    if args.json:
        args.json.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\nWrote {args.json}")


if __name__ == "__main__":
    main()
