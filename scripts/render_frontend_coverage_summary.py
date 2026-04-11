#!/usr/bin/env python3
"""Render frontend Jest coverage summary as Markdown."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

METRIC_NAMES: tuple[str, ...] = (
    "lines",
    "statements",
    "functions",
    "branches",
)


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Render the React/Jest coverage summary JSON as a Markdown section."
        )
    )
    parser.add_argument(
        "--summary-path",
        type=Path,
        default=Path("src/frontend/coverage/coverage-summary.json"),
        help="Path to the coverage-summary.json file.",
    )
    return parser


def load_total_summary(summary_path: Path) -> dict[str, dict[str, Any]] | None:
    """Load the total coverage summary block from the JSON report."""
    try:
        payload = json.loads(summary_path.read_text())
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None

    total = payload.get("total")
    if not isinstance(total, dict):
        return None
    return total


def format_metric(name: str, metric: dict[str, Any]) -> str:
    """Format a single coverage metric line for Markdown output."""
    pct = metric.get("pct", "Unknown")
    covered = metric.get("covered", 0)
    total = metric.get("total", 0)
    return f"- {name}: {pct}% ({covered}/{total})"


def render_markdown(summary_path: Path) -> str:
    """Render the frontend coverage summary section as Markdown."""
    lines = ["### Frontend tests", ""]
    total = load_total_summary(summary_path)
    if total is None:
        lines.append("_No frontend coverage data produced._")
        return "\n".join(lines)

    for metric_name in METRIC_NAMES:
        metric = total.get(metric_name)
        if not isinstance(metric, dict):
            continue
        lines.append(format_metric(metric_name, metric))

    if len(lines) == 2:
        lines.append("_No frontend coverage metrics were available._")

    return "\n".join(lines)


def main() -> int:
    """Run the CLI."""
    args = build_parser().parse_args()
    print(render_markdown(args.summary_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
