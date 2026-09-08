"""Command line entry point.

The model is a tool, not a report generator: inputs go in, results come out,
and any input can be changed without touching calculation code.

    python3 -m lca_film                                  full report
    python3 -m lca_film --table                          comparison table only
    python3 -m lca_film --list-scenarios                 what scenarios exist
    python3 -m lca_film --scenario harmonised_boundary   run one
    python3 -m lca_film --compare                        all scenarios side by side
    python3 -m lca_film --trace biofilm/composting       line-by-line arithmetic
    python3 -m lca_film --set biofilm/component/zein=2.0 ad-hoc what-if
    python3 -m lca_film --svg chart.svg --csv out.csv    write artefacts
    python3 -m lca_film --inputs other.toml              a different dataset
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from .calculate import evaluate_all
from .chart import render_svg
from .config import list_scenarios, load_study
from .report import (
    boundary_report,
    comparison_table,
    full_report,
    placeholder_register,
    qualitative_flags,
    scenario_comparison,
    sensitivity,
    trace,
)


def parse_set(assignment: str) -> dict:
    """Parse ``path=value`` from the command line into an override table.

    An ad-hoc override is deliberately tagged as a placeholder: a number typed
    at a shell prompt has no source behind it, and the flag should say so.
    """
    if "=" not in assignment:
        raise argparse.ArgumentTypeError(
            f"--set expects 'path=value', got {assignment!r} "
            f"(e.g. biofilm/component/zein=2.0)"
        )
    path, _, raw = assignment.partition("=")
    try:
        value = float(raw)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"--set value must be a number, got {raw!r}"
        ) from None
    return {
        "path": path.strip(),
        "value": value,
        "confidence": "placeholder",
        "source": "",
        "note": f"Set on the command line as --set {assignment}. No source.",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lca_film",
        description="Cradle-to-grave GHG comparison for anti-leak film materials.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--inputs",
        type=Path,
        default=None,
        help="path to an input TOML file (default: inputs.toml beside the package)",
    )
    parser.add_argument(
        "--scenario", default="default", help="named scenario from the input file"
    )
    parser.add_argument(
        "--set",
        dest="overrides",
        action="append",
        type=parse_set,
        default=[],
        metavar="PATH=VALUE",
        help="override one input, e.g. biofilm/component/alginate=6.0 (repeatable)",
    )
    parser.add_argument(
        "--list-scenarios", action="store_true", help="list scenarios and exit"
    )
    parser.add_argument(
        "--compare", action="store_true", help="all scenarios side by side"
    )
    parser.add_argument(
        "--trace",
        metavar="MATERIAL/ROUTE",
        default=None,
        help="line-by-line arithmetic for one result, e.g. biofilm/composting",
    )
    parser.add_argument("--table", action="store_true", help="print only the comparison table")
    parser.add_argument(
        "--boundaries", action="store_true", help="print only the boundary audit"
    )
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


def write_csv(path: Path, study, results) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "scenario",
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
                        study.scenario,
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
                    study.scenario,
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

    if args.list_scenarios:
        for name, spec in list_scenarios(args.inputs).items():
            print(f"{name}\n    {spec.get('label', '')}")
            description = spec.get("description", "")
            if description:
                print(f"    {description}")
            print()
        return 0

    if args.compare:
        names = list(list_scenarios(args.inputs))
        studies = [
            load_study(args.inputs, scenario=n, overrides=args.overrides) for n in names
        ]
        print("\n".join(scenario_comparison(studies)))
        return 0

    try:
        study = load_study(args.inputs, scenario=args.scenario, overrides=args.overrides)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    results = evaluate_all(study)

    if args.trace:
        if "/" not in args.trace:
            print(
                "error: --trace expects MATERIAL/ROUTE, e.g. biofilm/composting",
                file=sys.stderr,
            )
            return 2
        material_id, _, route_id = args.trace.partition("/")
        try:
            print("\n".join(trace(study, material_id, route_id)))
        except (KeyError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        return 0

    if args.svg:
        args.svg.write_text(
            render_svg(results, study.meta.get("title", ""), scenario=study.scenario_label),
            encoding="utf-8",
        )
        print(f"wrote {args.svg}", file=sys.stderr)
    if args.csv:
        write_csv(args.csv, study, results)
        print(f"wrote {args.csv}", file=sys.stderr)

    if args.table:
        print("\n".join(comparison_table(results)))
    elif args.boundaries:
        print("\n".join(boundary_report(study)))
    elif args.placeholders:
        print("\n".join(placeholder_register(results) + qualitative_flags(study)))
    elif args.sensitivity:
        print("\n".join(sensitivity(results)))
    elif not (args.svg or args.csv):
        print(full_report(study, results))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
