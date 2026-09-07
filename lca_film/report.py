"""Text reporting.

House rule for everything in here: a number is never printed without its
confidence tag, and any result built on a placeholder is marked at the point
the number appears -- not in a footnote further down the page.
"""

from __future__ import annotations

from typing import Sequence

from .calculate import Result, evaluate_all
from .config import Study
from .confidence import Confidence

RULE = "=" * 112
THIN = "-" * 112


def header(study: Study) -> list[str]:
    meta = study.meta
    out = [RULE, meta.get("title", "LCA comparison"), RULE]
    for key in ("functional_unit", "boundary", "gwp_method", "prepared"):
        if meta.get(key):
            out.append(f"{key.replace('_', ' ').title():<16}: {meta[key]}")
    out.append("")
    out.append("Confidence tags, shown against every number below:")
    for level in Confidence:
        out.append(f"  [{level.marker:<11}] {level.label}")
    out.append("")
    return out


def comparison_table(results: Sequence[Result]) -> list[str]:
    """The headline table: one row per material per end-of-life route."""
    out = [
        RULE,
        "CRADLE-TO-GRAVE COMPARISON  (kg CO2e per kg of film material)",
        RULE,
        f"{'Material / end-of-life route':<62}{'Total':>9}  "
        f"{'Range (low - high)':>22}  {'Weakest':<12} Flag",
        THIN,
    ]
    for r in results:
        rng = f"{r.total_low:.2f} - {r.total_high:.2f}"
        out.append(
            f"{r.label[:61]:<62}{r.total:>9.2f}  {rng:>22}  "
            f"{r.confidence.marker:<12} {r.flag}"
        )
    out.append(THIN)
    out.append(
        "A total is only as good as its weakest input. Rows marked "
        "!! PLACEHOLDER-BASED contain at least"
    )
    out.append(
        "one number with no source behind it and must not be compared against "
        "an unflagged row."
    )
    out.append("")
    return out


def breakdown(results: Sequence[Result]) -> list[str]:
    """Stage-by-stage account, so any total can be reconstructed by hand."""
    out = [RULE, "STAGE BREAKDOWN", RULE]
    seen_material = None
    for r in results:
        if r.material.id != seen_material:
            seen_material = r.material.id
            out.append("")
            out.append(f"{r.material.name}  ({r.material.role})")
            if r.material.summary:
                out.append(f"  {r.material.summary}")
            out.append("")
        out.append(f"  Route: {r.route.label}")
        for item in r.items:
            out.append(f"    {item.label:<54} {item.tagged:>18}")
            if item.note:
                for line in _wrap(item.note, 88):
                    out.append(f"        {line}")
        total_line = f"{r.total:+.2f} [{r.confidence.marker}]"
        out.append(f"    {'TOTAL':<54} {total_line:>18}   {r.flag}")
        out.append("")
    return out


def placeholder_register(results: Sequence[Result]) -> list[str]:
    """Everything still unsourced, and what fixing it would be worth."""
    out = [
        RULE,
        "PLACEHOLDER REGISTER  --  what still needs a source",
        RULE,
    ]
    seen: dict[str, tuple[str, float, float]] = {}
    for r in results:
        for item in r.placeholder_items:
            seen.setdefault(item.label, (item.note, item.low, item.high))
    if not seen:
        out.append("None. Every input is sourced, derived, or a tagged estimate.")
        out.append("")
        return out

    for label, (note, low, high) in seen.items():
        out.append(f"  * {label}")
        out.append(f"    Range carried through the model: {low:.2f} to {high:.2f} kg CO2e/kg")
        for line in _wrap(note, 92):
            out.append(f"    {line}")
        out.append("")
    return out


def qualitative_flags(study: Study) -> list[str]:
    """Impacts with no number, printed with the results because they are real."""
    out = [
        RULE,
        "QUALITATIVE FLAGS  --  real impacts that carry NO number and are absent from every total above",
        RULE,
    ]
    any_flag = False
    for material in study.materials:
        for flag in material.qualitative_flags:
            any_flag = True
            out.append(f"  [{flag.severity.upper()}] {material.name}: {flag.topic}")
            for line in _wrap(flag.text, 92):
                out.append(f"      {line}")
            out.append("")
    if not any_flag:
        out.append("  None recorded.")
        out.append("")
    return out


def ascii_chart(results: Sequence[Result], width: int = 52) -> list[str]:
    """Terminal bar chart, linear, with the tag on every bar."""
    out = [RULE, "COMPARISON CHART  (kg CO2e per kg, best end-of-life route per material)", RULE]

    best: dict[str, Result] = {}
    for r in results:
        current = best.get(r.material.id)
        if current is None or r.total < current.total:
            best[r.material.id] = r

    rows = list(best.values())
    peak = max(abs(r.total) for r in rows) or 1.0
    for r in rows:
        filled = max(1, round(width * abs(r.total) / peak))
        bar = "#" * filled
        out.append(f"  {r.material.name[:44]:<45} {r.total:>8.2f} [{r.confidence.marker}]")
        out.append(f"  {'':<45} {bar} {r.flag}")
        out.append(f"  {'':<45} route: {r.route_label}")
        out.append("")
    out.append(
        "  Bars are the LOWEST-emitting end-of-life route for each material. "
        "Flagged bars are not"
    )
    out.append("  comparable with unflagged ones at face value.")
    out.append("")
    return out


def sensitivity(results: Sequence[Result]) -> list[str]:
    """Where the uncertainty actually lives, ranked by how much it moves."""
    out = [RULE, "SENSITIVITY  --  which inputs move the answer most", RULE]
    contributions: dict[str, tuple[float, Confidence, str]] = {}
    for r in results:
        for item in r.items:
            spread = item.high - item.low
            key = f"{r.material.name}: {item.label}"
            prev = contributions.get(key)
            if prev is None or spread > prev[0]:
                contributions[key] = (spread, item.confidence, r.material.name)

    ranked = sorted(contributions.items(), key=lambda kv: kv[1][0], reverse=True)
    out.append(f"{'Input':<64}{'Range width':>14}  Tag")
    out.append(THIN)
    for key, (spread, tag, _material) in ranked:
        if spread <= 0:
            continue
        out.append(f"{key[:63]:<64}{spread:>14.2f}  [{tag.marker}]")
    out.append(THIN)
    out.append(
        "Range width is high bound minus low bound, in kg CO2e/kg. "
        "The top row is where to spend"
    )
    out.append("effort next: it is the input whose uncertainty dominates the comparison.")
    out.append("")
    return out


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def full_report(study: Study, results: Sequence[Result] | None = None) -> str:
    results = list(results) if results is not None else evaluate_all(study)
    sections = [
        header(study),
        comparison_table(results),
        ascii_chart(results),
        breakdown(results),
        sensitivity(results),
        placeholder_register(results),
        qualitative_flags(study),
    ]
    return "\n".join(line for section in sections for line in section)
