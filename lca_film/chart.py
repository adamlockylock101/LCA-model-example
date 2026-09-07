"""Dependency-free SVG chart.

Written by hand rather than with matplotlib so the tool runs anywhere Python
does, with nothing to install. Placeholder-based bars are drawn hatched and
labelled, so a result that rests on an unsourced number cannot be screenshotted
out of context and mistaken for a solid one.
"""

from __future__ import annotations

import html
from typing import Sequence

from .calculate import Result

BAR_H = 26
GAP = 12
PAD_TOP = 96
PAD_LEFT = 320
PAD_RIGHT = 190
PAD_BOTTOM = 76

FILL = {
    "ldpe": "#6b7280",
    "pva": "#2563eb",
    "biofilm": "#059669",
}
FALLBACK_FILL = "#9333ea"


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def render_svg(results: Sequence[Result], title: str = "") -> str:
    """Horizontal bar chart of totals, with ranges as whiskers."""
    rows = list(results)
    height = PAD_TOP + len(rows) * (BAR_H + GAP) + PAD_BOTTOM
    plot_w = 620
    width = PAD_LEFT + plot_w + PAD_RIGHT

    # Scale on the central values; ranges can run far past the bars, so they are
    # drawn clipped rather than allowed to squash every bar into invisibility.
    peak = max([r.total for r in rows] + [0.0]) or 1.0
    peak *= 1.08

    def x(value: float) -> float:
        return PAD_LEFT + max(0.0, min(value, peak)) / peak * plot_w

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="ui-sans-serif, system-ui, '
        f'Helvetica, Arial, sans-serif">',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        '<defs>'
        '<pattern id="ph" width="7" height="7" patternTransform="rotate(45)" '
        'patternUnits="userSpaceOnUse">'
        '<rect width="7" height="7" fill="#ffffff" fill-opacity="0.55"/>'
        '<line x1="0" y1="0" x2="0" y2="7" stroke="#ffffff" stroke-width="3.2"/>'
        '</pattern></defs>',
    ]

    if title:
        parts.append(
            f'<text x="24" y="34" font-size="17" font-weight="700" fill="#111827">'
            f"{_esc(title)}</text>"
        )
    parts.append(
        '<text x="24" y="57" font-size="12" fill="#4b5563">'
        "Cradle-to-grave kg CO2e per kg of film material. Whiskers show the "
        "low-high range carried by the inputs.</text>"
    )
    parts.append(
        '<text x="24" y="75" font-size="12" fill="#b91c1c" font-weight="600">'
        "Hatched bars are PLACEHOLDER-BASED: at least one input has no source. "
        "Not comparable at face value.</text>"
    )

    # Gridlines.
    step = _nice_step(peak)
    tick = 0.0
    while tick <= peak + 1e-9:
        gx = x(tick)
        parts.append(
            f'<line x1="{gx:.1f}" y1="{PAD_TOP - 12}" x2="{gx:.1f}" '
            f'y2="{height - PAD_BOTTOM + 6}" stroke="#e5e7eb" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{gx:.1f}" y="{height - PAD_BOTTOM + 22}" font-size="11" '
            f'fill="#6b7280" text-anchor="middle">{tick:g}</text>'
        )
        tick += step

    for index, result in enumerate(rows):
        y = PAD_TOP + index * (BAR_H + GAP)
        bar_end = x(result.total)
        colour = FILL.get(result.material.id, FALLBACK_FILL)

        label = f"{result.material.name} -- {result.route_label}"
        parts.append(
            f'<text x="{PAD_LEFT - 12}" y="{y + BAR_H * 0.68:.1f}" font-size="12" '
            f'fill="#111827" text-anchor="end">{_esc(_shorten(label, 52))}</text>'
        )

        parts.append(
            f'<rect x="{PAD_LEFT}" y="{y}" width="{bar_end - PAD_LEFT:.1f}" '
            f'height="{BAR_H}" fill="{colour}" rx="3"/>'
        )
        if result.is_placeholder_based:
            parts.append(
                f'<rect x="{PAD_LEFT}" y="{y}" width="{bar_end - PAD_LEFT:.1f}" '
                f'height="{BAR_H}" fill="url(#ph)" rx="3"/>'
                f'<rect x="{PAD_LEFT}" y="{y}" width="{bar_end - PAD_LEFT:.1f}" '
                f'height="{BAR_H}" fill="none" stroke="#b91c1c" stroke-width="1.6" rx="3"/>'
            )

        # Range whisker.
        lo, hi = x(result.total_low), x(result.total_high)
        mid = y + BAR_H / 2
        parts.append(
            f'<line x1="{lo:.1f}" y1="{mid:.1f}" x2="{hi:.1f}" y2="{mid:.1f}" '
            f'stroke="#111827" stroke-width="1.4" stroke-opacity="0.75"/>'
            f'<line x1="{lo:.1f}" y1="{mid - 6:.1f}" x2="{lo:.1f}" y2="{mid + 6:.1f}" '
            f'stroke="#111827" stroke-width="1.4" stroke-opacity="0.75"/>'
        )
        if result.total_high <= peak:
            parts.append(
                f'<line x1="{hi:.1f}" y1="{mid - 6:.1f}" x2="{hi:.1f}" '
                f'y2="{mid + 6:.1f}" stroke="#111827" stroke-width="1.4" '
                f'stroke-opacity="0.75"/>'
            )
        else:
            # Range runs off the chart; say so rather than silently clipping.
            parts.append(
                f'<text x="{hi + 4:.1f}" y="{mid + 4:.1f}" font-size="11" '
                f'fill="#b91c1c">&#8594; {result.total_high:.0f}</text>'
            )

        tag = result.confidence.marker
        value_x = bar_end + (58 if result.total_high > peak else 12)
        parts.append(
            f'<text x="{value_x:.1f}" y="{y + BAR_H * 0.68:.1f}" font-size="12" '
            f'font-weight="600" fill="#111827">{result.total:.2f} '
            f'<tspan fill="#6b7280" font-weight="400">[{tag}]</tspan></text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def _nice_step(peak: float) -> float:
    for step in (0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500):
        if peak / step <= 8:
            return float(step)
    return peak / 8


def _shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"
