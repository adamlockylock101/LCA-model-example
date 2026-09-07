"""Command line entry point.

    python -m lca_film                        full report to stdout
    python -m lca_film --table                just the comparison table
    python -m lca_film --svg chart.svg        write the chart
    python -m lca_film --csv results.csv      write results for a spreadsheet
    python -m lca_film --inputs other.toml    run against a different data file
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from .calculate import evaluate_all
from .chart import render_svg
from .config import load_study
from .report import (
    comparison_table,
    full_report,
    placeholder_register,
    qualitative_flags,
    sensitivity,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lca_film",
        description="Cradle-to-grave GHG comparison for anti-leak film materials.",
    )
    parser.add_argument(
        "--inputs",
        type=Path,
        default=None,
        help="path to an input TOML file (default: inputs.toml beside the package)",
    )
    parser.add_argument("--table", action="store_true", help="print only the comparison table")
    parser.add_argument(
        "--placeholders",
        action="store_true",
        help="print only the placeholder register and qualitative flags",
    )
    parser.add_argument(
        "--sensitivity", action="store_true", help="print only the sensitivity ranking"
    )
    parser.add_argument("--svg", type=Path, default=None, help="write an SVG chart to this path")
    parser.add_argument("--csv", type=Path, default=None, help="write results as CSV to this path")
    return parser


def write_csv(path: Path, results) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "material",
                "end_of_life_route",
                "stage",
                "value_kgco2e_per_kg",
                "confidence",
                "low",
                "high",
                "placeholder_based_result",
                "note",
            ]
        )
        for r in results:
            for item in r.items:
                writer.writerow(
                    [
                        r.material.name,
                        r.route_label,
                        item.label,
                        f"{item.value:.4f}",
                        item.confidence.marker,
                        f"{item.low:.4f}",
                        f"{item.high:.4f}",
                        "YES" if r.is_placeholder_based else "no",
                        item.note,
                    ]
                )
            writer.writerow(
                [
                    r.material.name,
                    r.route_label,
                    "TOTAL",
                    f"{r.total:.4f}",
                    r.confidence.marker,
                    f"{r.total_low:.4f}",
                    f"{r.total_high:.4f}",
                    "YES" if r.is_placeholder_based else "no",
                    "",
                ]
            )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    study = load_study(args.inputs)
    results = evaluate_all(study)

    if args.svg:
        args.svg.write_text(
            render_svg(results, study.meta.get("title", "")), encoding="utf-8"
        )
        print(f"wrote {args.svg}", file=sys.stderr)
    if args.csv:
        write_csv(args.csv, results)
        print(f"wrote {args.csv}", file=sys.stderr)

    if args.table:
        print("\n".join(comparison_table(results)))
    elif args.placeholders:
        print("\n".join(placeholder_register(results) + qualitative_flags(study)))
    elif args.sensitivity:
        print("\n".join(sensitivity(results)))
    elif not (args.svg or args.csv):
        print(full_report(study, results))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
