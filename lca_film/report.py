"""Text reporting.

House rule for everything in here: a number is never printed without its
confidence tag, and any result built on a placeholder is marked at the point
the number appears -- not in a footnote further down the page.
"""

from __future__ import annotations

from typing import Sequence

from .boundary import DESCRIPTIONS
from .calculate import Result, evaluate, evaluate_all
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
    out.append(f"{'Scenario':<16}: {study.scenario} -- {study.scenario_label}")
    if study.scenario_description:
        for line in _wrap(study.scenario_description, 92):
            out.append(f"{'':<18}{line}")
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
            for driver in item.unquantified:
                for line in _wrap(f"UNQUANTIFIED: {driver}", 88):
                    out.append(f"        {line}")
        total_line = f"{r.total:+.2f} [{r.confidence.marker}]"
        out.append(f"    {'TOTAL':<54} {total_line:>18}   {r.flag}")
        out.append("")
    return out


def placeholder_register(results: Sequence[Result]) -> list[str]:
    """Everything still unsourced, and what fixing it would be worth."""
    out = [
        RULE,
        "UNVERIFIABLE INPUTS  --  placeholders needing a source, and recalled values",
        RULE,
    ]
    seen: dict[str, tuple[str, float, float]] = {}
    for r in results:
        for item in r.unverified_items:
            key = f"[{item.confidence.marker}] {item.label}"
            seen.setdefault(key, (item.note, item.low, item.high))
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
    out.append(
        "This ranks PARAMETRIC spread only -- how much one quantity could vary. "
        "It does not"
    )
    out.append(
        "rank scope disagreement (see SCOPE VARIANTS) or named drivers that "
        "carry no range"
    )
    out.append("(see UNQUANTIFIED UNCERTAINTY). A short bar here is not a settled input.")
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
        boundary_report(study),
        ascii_chart(results),
        breakdown(results),
        sensitivity(results),
        scope_report(study),
        unquantified_report(study),
        placeholder_register(results),
        qualitative_flags(study),
    ]
    return "\n".join(line for section in sections for line in section)


def boundary_report(study: Study) -> list[str]:
    """Inputs measured on a different system boundary than the study targets.

    Separate from the confidence system on purpose. Confidence answers "how well
    do we know this number"; boundary answers "is this number even the right
    quantity to be adding here". A value can score perfectly on the first and
    still fail the second, and that is the more dangerous failure.
    """
    issues = study.boundary_issues()
    out = [
        RULE,
        "BOUNDARY AUDIT  --  are these numbers measuring the same thing?",
        RULE,
        f"Study target boundary: {study.target_boundary!r}",
        f"  {DESCRIPTIONS.get(study.target_boundary, '')}",
        "",
    ]
    if not issues:
        out.append("  No mismatches. Every raw-material input is on the target boundary.")
        out.append("")
        return out

    out.append(f"  {len(issues)} input(s) NOT on the target boundary:")
    out.append("")
    for issue in issues:
        for line in _wrap(issue.describe(), 92):
            out.append(f"    {line}")
        out.append(f"      {DESCRIPTIONS.get(issue.found, '')}")
        out.append("")
    out.append(
        "  A mismatch is not a rounding error. It means the totals for that material "
        "are not"
    )
    out.append(
        "  like-for-like with the others, no matter how well sourced each individual "
        "number is."
    )
    out.append("")
    return out


def trace(study: Study, material_id: str, route_id: str) -> list[str]:
    """Line-by-line audit trail for one material on one route.

    Prints the arithmetic, not just the answer, so any total in this model can
    be checked by hand against its inputs.
    """
    material = study.material(material_id)
    try:
        route = next(r for r in material.eol_routes if r.id == route_id)
    except StopIteration:
        available = ", ".join(r.id for r in material.eol_routes)
        raise KeyError(
            f"material '{material_id}' has no end-of-life route '{route_id}'; "
            f"available: {available}"
        ) from None

    result = evaluate(material, route, study.constants)
    out = [
        RULE,
        f"AUDIT TRACE  --  {material.name}  /  {route.label}",
        f"Scenario: {study.scenario} ({study.scenario_label})",
        RULE,
        "",
    ]

    if material.is_blend:
        out.append("STEP 1. Raw materials, built up from the formulation")
        out.append("")
        out.append(
            f"  {'Component':<18}{'Dry g':>7}{'Frac':>8}{'kg CO2e/kg':>12}"
            f"{'Contribution':>14}{'Range width':>13}  {'Tag':<13}Boundary"
        )
        out.append("  " + "-" * 108)
        subtotal = 0.0
        spread_total = 0.0
        for c in material.composition:
            contribution = c.mass_fraction.value * c.footprint.value
            spread = c.mass_fraction.value * (
                c.footprint.high_or_value - c.footprint.low_or_value
            )
            subtotal += contribution
            spread_total += spread
            tag = f"[{c.footprint.confidence.marker}]"
            grams = "-" if c.dry_mass_g is None else f"{c.dry_mass_g:.1f}"
            out.append(
                f"  {c.name:<18}{grams:>7}{c.mass_fraction.value:>8.4f}"
                f"{c.footprint.value:>12.2f}{contribution:>14.4f}{spread:>13.4f}  "
                f"{tag:<13}{c.footprint.boundary}"
            )
            if c.footprint.overridden_by:
                out.append(f"  {'':<18}  overridden by scenario: {c.footprint.overridden_by}")
        out.append("  " + "-" * 108)
        out.append(
            f"  {'Raw material subtotal':<18}{'':>27}{subtotal:>14.4f}{spread_total:>13.4f}"
        )
        out.append("")
        out.append(
            "  'Range width' is that component's share of the raw-material range: "
            "its mass"
        )
        out.append(
            "  fraction times its own low-to-high span. It is how much this "
            "component alone"
        )
        out.append("  could move the total, and so which one is worth resolving next.")
        out.append("")
    else:
        out.append("STEP 1. Raw material (given directly, not a blend)")
        out.append("")

    out.append("STEP 2. Full account")
    out.append("")
    running = 0.0
    for index, item in enumerate(result.items, start=1):
        running += item.value
        out.append(
            f"  {index}. {item.label:<50}{item.value:>+10.4f}  "
            f"[{item.confidence.marker:<11}]  running total {running:>+9.4f}"
        )
        if item.note:
            for line in _wrap(item.note, 84):
                out.append(f"         {line}")
        out.append("")

    out.append("  " + "=" * 96)
    out.append(
        f"  {'TOTAL':<53}{result.total:>+10.4f}  "
        f"[{result.confidence.marker:<11}]  {result.flag}"
    )
    out.append(
        f"  {'Range across input bounds':<53}"
        f"{result.total_low:>10.2f} to {result.total_high:.2f}"
    )
    out.append("")

    credit = [i for i in result.items if i.kind == "biogenic_credit"]
    release = [i for i in result.items if i.kind == "eol_biogenic"]
    out.append("STEP 3. Biogenic carbon check")
    out.append("")
    if not credit:
        out.append(
            "  No biogenic carbon credit applied. This material has no biogenic "
            "carbon content,"
        )
        out.append("  so there is nothing to credit and nothing to return at end of life.")
    else:
        out.append(f"  Credit applied at uptake       {credit[0].value:>+10.4f}")
        if release:
            out.append(f"  Returned at end of life        {release[0].value:>+10.4f}")
            net = credit[0].value + release[0].value
            out.append(f"  Net biogenic carbon            {net:>+10.4f}")
            out.append("")
            if net > 0:
                out.append(
                    "  Net POSITIVE: the methane fraction of the released carbon costs "
                    "more than the"
                )
                out.append("  carbon retained in compost is worth.")
            elif net < 0:
                out.append(
                    "  Net NEGATIVE: some carbon stays sequestered rather than being "
                    "released."
                )
            else:
                out.append("  Net zero: everything credited at uptake is returned at end of life.")
    out.append("")
    return out


def scenario_comparison(
    studies: Sequence[Study], material_id: str | None = None
) -> list[str]:
    """Same materials and routes, side by side across scenarios."""
    out = [RULE, "SCENARIO COMPARISON  (kg CO2e per kg)", RULE]
    names = [s.scenario for s in studies]
    out.append(f"{'Material / route':<46}" + "".join(f"{n[:20]:>21}" for n in names))
    out.append(THIN)

    rows: dict[str, list] = {}
    for study in studies:
        for result in evaluate_all(study):
            if material_id and result.material.id != material_id:
                continue
            rows.setdefault(result.label, []).append(result)

    for label, results in rows.items():
        cells = "".join(
            f"{r.total:>15.2f} [{r.confidence.marker[:3]}]" for r in results
        )
        out.append(f"{label[:45]:<46}{cells}")
    out.append(THIN)
    for study in studies:
        out.append(f"  {study.scenario}: {study.scenario_label}")
    out.append("")
    return out


def _quantities(study: Study):
    """Every Quantity in the study, with the material it belongs to."""
    for material in study.materials:
        for stage in material.stages:
            yield material, stage
        for component in material.composition:
            yield material, component.footprint
        for route in material.eol_routes:
            yield material, route.fossil


def scope_report(study: Study) -> list[str]:
    """Published numbers that measure something OTHER than the input they sit near.

    These used to be folded into low/high, which quietly turned "this source
    measured a different product" into "we are uncertain by 5x". They are listed
    here instead, with what each one actually measured, so the difference in
    kind stays visible.
    """
    out = [
        RULE,
        "SCOPE VARIANTS  --  other published figures that are NOT this quantity",
        RULE,
    ]
    found = False
    for material, quantity in _quantities(study):
        if not quantity.scope_variants:
            continue
        found = True
        out.append(f"  {material.name} -- {quantity.label}")
        out.append(f"    In use: {quantity.value:.2f} on the {quantity.boundary!r} boundary")
        out.append("")
        for variant in quantity.scope_variants:
            verdict = "COMPARABLE" if variant.comparable else "NOT COMPARABLE"
            out.append(
                f"    [{verdict}] {variant.label}: {variant.span} "
                f"[{variant.confidence.marker}]"
            )
            for field, value in (
                ("product", variant.product),
                ("feedstock", variant.feedstock),
                ("includes", variant.includes),
                ("excludes", variant.excludes),
            ):
                if value:
                    out.append(f"        {field:<10} {value}")
            if variant.why_not_comparable:
                for line in _wrap(f"why not a bound: {variant.why_not_comparable}", 84):
                    out.append(f"        {line}")
            out.append("")
        out.append("")
    if not found:
        out.append("  None recorded.")
        out.append("")
        return out
    out.append(
        "  A scope variant is NOT a bound. It is a different measurement, kept "
        "visible so the"
    )
    out.append(
        "  reader can see what else the literature says without it masquerading "
        "as uncertainty."
    )
    out.append("")
    return out


def unquantified_report(study: Study) -> list[str]:
    """Uncertainty drivers that are real but carry no number.

    Without this section a narrow low/high reads as confidence. Two sources
    agreeing to within 2% says they agree; it does not say the quantity is known
    to within 2%, and where the reasons for that are known they are named here.
    """
    out = [
        RULE,
        "UNQUANTIFIED UNCERTAINTY  --  real drivers that low/high does NOT capture",
        RULE,
    ]
    found = False
    for material, quantity in _quantities(study):
        if not quantity.unquantified:
            continue
        found = True
        spread = quantity.high_or_value - quantity.low_or_value
        out.append(
            f"  {material.name} -- {quantity.label}  "
            f"({quantity.value:.2f}, stated range width {spread:.2f})"
        )
        for driver in quantity.unquantified:
            for index, line in enumerate(_wrap(driver, 88)):
                out.append(f"      {'- ' if index == 0 else '  '}{line}")
        out.append("")
    if not found:
        out.append("  None recorded.")
        out.append("")
        return out
    out.append(
        "  Do NOT read a narrow range on these inputs as a small uncertainty. "
        "The range covers"
    )
    out.append(
        "  what the sources disagree about; the drivers above are what none of "
        "them pins down."
    )
    out.append("")
    return out
