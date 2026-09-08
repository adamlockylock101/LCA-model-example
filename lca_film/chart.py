"""Dependency-free SVG chart.

Written by hand rather than with matplotlib so the tool runs anywhere Python
does, with nothing to install. Rendered from live model output: change an input
and rerun, and the chart changes with it.

Layout rule that keeps it readable: values and tags live in a FIXED column to
the right of the plot area, never at the end of the bar. Bar-end labels collide
as soon as two bars are similar lengths or one runs off scale, so they are not
used. Ranges that exceed the axis are drawn as a chevron at the plot edge and
stated in full in the value column rather than being silently clipped.

Colours are the validated categorical slots 1-3 (blue / orange / aqua), assigned
by material identity and fixed, so a material keeps its hue across scenarios.
Placeholder-based bars carry a 45-degree texture and a red outline, so the
warning survives being screenshotted out of context.
"""

from __future__ import annotations

import html
from typing import Sequence

from .calculate import Result

# Geometry
PAD_LEFT = 250
PLOT_W = 540
VALUE_COL_W = 230
PAD_RIGHT = 24
PAD_TOP = 150
PAD_BOTTOM = 74
BAR_H = 20
ROW_H = 34
GROUP_GAP = 12
GROUP_HEAD_H = 22

VALUE_X = PAD_LEFT + PLOT_W + 26
WIDTH = VALUE_X + VALUE_COL_W + PAD_RIGHT

# Validated categorical slots 1-3, light and dark steps.
SERIES = {
    "ldpe": ("#2a78d6", "#3987e5"),
    "pva": ("#eb6834", "#d95926"),
    "biofilm": ("#1baf7a", "#199e70"),
}
FALLBACK = ("#4a3aa7", "#9085e9")


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _style() -> str:
    """Theme-aware tokens. Dark steps are selected for the dark surface."""
    return """<style>
  .viz { --surface: #fcfcfb; --ink: #0b0b0b; --ink-2: #52514e; --ink-3: #85837c;
         --grid: #e4e3df; --alert: #c0342f; --rule: #d8d7d2;
         --s-ldpe: #2a78d6; --s-pva: #eb6834; --s-biofilm: #1baf7a; --s-other: #4a3aa7; }
  @media (prefers-color-scheme: dark) {
    .viz { --surface: #1a1a19; --ink: #ffffff; --ink-2: #c3c2b7; --ink-3: #93918a;
           --grid: #33322f; --alert: #e66767; --rule: #3d3c38;
           --s-ldpe: #3987e5; --s-pva: #d95926; --s-biofilm: #199e70; --s-other: #9085e9; }
  }
  .surface { fill: var(--surface); }
  .t-title { fill: var(--ink); font-size: 17px; font-weight: 700; }
  .t-sub   { fill: var(--ink-2); font-size: 12px; }
  .t-muted { fill: var(--ink-3); font-size: 11px; }
  .t-alert { fill: var(--alert); font-size: 11.5px; font-weight: 600; }
  .t-row   { fill: var(--ink); font-size: 12px; }
  .t-val   { fill: var(--ink); font-size: 12.5px; font-weight: 600; }
  .t-tag   { fill: var(--ink-3); font-size: 11px; font-weight: 400; }
  .grid    { stroke: var(--grid); stroke-width: 1; }
  .rule    { stroke: var(--rule); stroke-width: 1; }
  .whisker { stroke: var(--ink-2); stroke-width: 1.4; stroke-opacity: 0.8; }
  .flagged { fill: none; stroke: var(--alert); stroke-width: 1.6; }
</style>"""


def render_svg(
    results: Sequence[Result], title: str = "", scenario: str = ""
) -> str:
    rows = list(results)
    if not rows:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>'

    # Group rows by material so a separator can sit between groups.
    groups: list[tuple[str, list[Result]]] = []
    for row in rows:
        if groups and groups[-1][0] == row.material.id:
            groups[-1][1].append(row)
        else:
            groups.append((row.material.id, [row]))

    height = (
        PAD_TOP
        + len(rows) * ROW_H
        + len(groups) * (GROUP_GAP + GROUP_HEAD_H)
        + PAD_BOTTOM
    )

    peak = _axis_peak(rows)
    step = _nice_step(peak)

    def x(value: float) -> float:
        return PAD_LEFT + max(0.0, min(value, peak)) / peak * PLOT_W

    p: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
        f'viewBox="0 0 {WIDTH} {height}" class="viz" '
        f'font-family="ui-sans-serif, system-ui, Helvetica, Arial, sans-serif" '
        f'role="img" aria-label="{_esc(title)}">',
        _style(),
        '<defs><pattern id="ph" width="6" height="6" patternTransform="rotate(45)" '
        'patternUnits="userSpaceOnUse">'
        '<rect width="6" height="6" fill="#ffffff" fill-opacity="0.34"/>'
        '<line x1="0" y1="0" x2="0" y2="6" stroke="#ffffff" stroke-opacity="0.62" '
        'stroke-width="3"/></pattern></defs>',
        f'<rect class="surface" width="{WIDTH}" height="{height}"/>',
    ]

    if title:
        p.append(f'<text class="t-title" x="24" y="32">{_esc(title)}</text>')
    p.append(
        '<text class="t-sub" x="24" y="54">Cradle-to-grave kg CO2e per kg of film '
        "material. Bars are central values; whiskers span the input ranges.</text>"
    )
    if scenario:
        p.append(
            f'<text class="t-sub" x="24" y="72">Scenario: '
            f"<tspan font-weight=\"600\">{_esc(scenario)}</tspan></text>"
        )
    p.append(
        '<text class="t-alert" x="24" y="92">Hatched bars carry an input that '
        "cannot be checked against an external record - see the tag on each "
        "value. Not comparable at face value.</text>"
    )

    # Legend: identity is never carried by colour alone, but a legend is still
    # required for more than one series.
    legend_x = 24.0
    for material_id, group in groups:
        name = group[0].material.name.split(" (")[0]
        token = SERIES.get(material_id, FALLBACK)
        var = f"--s-{material_id}" if material_id in SERIES else "--s-other"
        p.append(
            f'<rect x="{legend_x}" y="106" width="10" height="10" rx="2" '
            f'fill="var({var}, {token[0]})"/>'
        )
        p.append(
            f'<text class="t-sub" x="{legend_x + 16}" y="115">{_esc(name)}</text>'
        )
        legend_x += 42 + len(name) * 7.0

    plot_top = PAD_TOP - 16
    plot_bottom = height - PAD_BOTTOM + 4

    tick = 0.0
    while tick <= peak + 1e-9:
        gx = x(tick)
        p.append(
            f'<line class="grid" x1="{gx:.1f}" y1="{plot_top}" '
            f'x2="{gx:.1f}" y2="{plot_bottom}"/>'
        )
        p.append(
            f'<text class="t-sub" x="{gx:.1f}" y="{plot_bottom + 18}" '
            f'text-anchor="middle">{tick:g}</text>'
        )
        tick += step
    p.append(
        f'<text class="t-muted" x="{PAD_LEFT + PLOT_W / 2:.0f}" '
        f'y="{plot_bottom + 34}" text-anchor="middle">kg CO2e per kg</text>'
    )

    y = float(PAD_TOP)
    for group_index, (material_id, group) in enumerate(groups):
        if group_index:
            p.append(
                f'<line class="rule" x1="24" y1="{y - GROUP_GAP / 2:.1f}" '
                f'x2="{WIDTH - 24}" y2="{y - GROUP_GAP / 2:.1f}"/>'
            )
        var = f"--s-{material_id}" if material_id in SERIES else "--s-other"
        fallback = SERIES.get(material_id, FALLBACK)[0]

        # Material named once per group, so row labels carry only the route and
        # never need truncating.
        p.append(
            f'<text class="t-row" x="24" y="{y + 12:.1f}" font-weight="700">'
            f"{_esc(group[0].material.name)}</text>"
        )
        y += GROUP_HEAD_H

        for row in group:
            bar_end = x(row.total)
            bar_w = max(2.0, bar_end - PAD_LEFT)
            mid = y + BAR_H / 2

            p.append(
                f'<text class="t-row" x="{PAD_LEFT - 14}" y="{mid + 4:.1f}" '
                f'text-anchor="end" fill="var(--ink-2)">'
                f"{_esc(_shorten(row.route_label, 34))}</text>"
            )
            p.append(
                f'<rect x="{PAD_LEFT}" y="{y:.1f}" width="{bar_w:.1f}" '
                f'height="{BAR_H}" rx="4" fill="var({var}, {fallback})"/>'
            )
            if row.is_unverified_based:
                p.append(
                    f'<rect x="{PAD_LEFT}" y="{y:.1f}" width="{bar_w:.1f}" '
                    f'height="{BAR_H}" rx="4" fill="url(#ph)"/>'
                    f'<rect class="flagged" x="{PAD_LEFT}" y="{y:.1f}" '
                    f'width="{bar_w:.1f}" height="{BAR_H}" rx="4"/>'
                )

            lo, hi = x(row.total_low), x(row.total_high)
            p.append(
                f'<line class="whisker" x1="{lo:.1f}" y1="{mid:.1f}" '
                f'x2="{hi:.1f}" y2="{mid:.1f}"/>'
                f'<line class="whisker" x1="{lo:.1f}" y1="{mid - 5:.1f}" '
                f'x2="{lo:.1f}" y2="{mid + 5:.1f}"/>'
            )
            if row.total_high <= peak:
                p.append(
                    f'<line class="whisker" x1="{hi:.1f}" y1="{mid - 5:.1f}" '
                    f'x2="{hi:.1f}" y2="{mid + 5:.1f}"/>'
                )
            else:
                # Off-scale: a chevron at the plot edge, with the real number
                # spelled out in the value column. Never silently clipped.
                edge = PAD_LEFT + PLOT_W
                p.append(
                    f'<path d="M{edge - 8:.1f} {mid - 5:.1f} L{edge - 2:.1f} '
                    f'{mid:.1f} L{edge - 8:.1f} {mid + 5:.1f}" fill="none" '
                    f'stroke="var(--alert)" stroke-width="1.8"/>'
                )

            # Fixed value column -- the reason nothing overlaps.
            p.append(
                f'<text class="t-val" x="{VALUE_X}" y="{mid - 1:.1f}">'
                f'{row.total:.2f}'
                f'<tspan class="t-tag" dx="6">[{row.confidence.marker}]</tspan></text>'
            )
            range_text = f"range {row.total_low:.2f} to {row.total_high:.2f}"
            cls = "t-alert" if row.total_high > peak else "t-muted"
            p.append(
                f'<text class="{cls}" x="{VALUE_X}" y="{mid + 12:.1f}" '
                f'font-size="10.5" font-weight="400">{range_text}</text>'
            )
            y += ROW_H
        y += GROUP_GAP

    p.append("</svg>")
    return "\n".join(p)


def _axis_peak(rows: Sequence[Result]) -> float:
    """Where to end the axis.

    Sized to fit the central values AND any range that is merely wide, but not
    a range that is orders of magnitude out -- one such outlier would squash
    every other bar to a stub. Ranges beyond the cutoff run off-scale and are
    marked with a chevron and stated in full in the value column, so nothing is
    hidden by the choice.
    """
    top = max((r.total for r in rows), default=1.0)
    top = top if top > 0 else 1.0
    cutoff = top * 3.0
    in_scale = [r.total_high for r in rows if r.total_high <= cutoff]
    return max(top, max(in_scale, default=top)) * 1.06


def _nice_step(peak: float) -> float:
    for step in (0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500):
        if peak / step <= 8:
            return float(step)
    return peak / 8


def _shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"
