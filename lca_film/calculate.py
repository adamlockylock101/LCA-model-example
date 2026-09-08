"""The calculation itself.

Deliberately kept free of any numbers. Every figure arrives from
:mod:`lca_film.config`; this module only combines them and carries the
confidence tags along.

Cradle-to-grave total for one material on one end-of-life route:

    raw material
  + processing
  + biogenic carbon credit        (negative; uptake into the material)
  + end-of-life fossil burden
  + end-of-life biogenic release  (returns the credited carbon)
  = total

The biogenic credit and the biogenic release are both computed from the same
carbon content, so a change to the formulation moves both together. For a fully
mineralised biogenic material they cancel to roughly zero, which is the
behaviour a reader should be able to check by eye.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Optional, Sequence

from .config import Constants, Study
from .confidence import Confidence, weakest
from .model import EndOfLifeRoute, Material, Quantity


@dataclass(frozen=True)
class LineItem:
    """One row of a material's carbon account, with its tag attached."""

    kind: str
    label: str
    value: float
    confidence: Confidence
    low: float
    high: float
    note: str = ""
    unquantified: tuple[str, ...] = ()

    @property
    def has_unquantified(self) -> bool:
        """True when low/high does NOT capture everything that could move this."""
        return bool(self.unquantified)

    @property
    def tagged(self) -> str:
        return f"{self.value:+.2f} [{self.confidence.marker}]"


@dataclass(frozen=True)
class Result:
    material: Material
    route: EndOfLifeRoute
    items: Sequence[LineItem]

    @property
    def total(self) -> float:
        return sum(i.value for i in self.items)

    @property
    def total_low(self) -> float:
        return sum(i.low for i in self.items)

    @property
    def total_high(self) -> float:
        return sum(i.high for i in self.items)

    @property
    def confidence(self) -> Confidence:
        return weakest(i.confidence for i in self.items)

    @property
    def placeholder_items(self) -> list[LineItem]:
        return [i for i in self.items if i.confidence.is_placeholder]

    @property
    def is_placeholder_based(self) -> bool:
        return bool(self.placeholder_items)

    @property
    def flag(self) -> str:
        """The visible warning that rides alongside every placeholder result."""
        return "!! PLACEHOLDER-BASED" if self.is_placeholder_based else ""

    @property
    def route_label(self) -> str:
        """Route name without the redundant 'End of life:' prefix."""
        label = self.route.label
        prefix = "End of life:"
        return label[len(prefix):].strip() if label.startswith(prefix) else label

    @property
    def label(self) -> str:
        return f"{self.material.name} -- {self.route_label}"


def _item_from_quantity(kind: str, q: Quantity) -> LineItem:
    return LineItem(
        kind=kind,
        label=q.label,
        value=q.value,
        confidence=q.confidence,
        low=q.low_or_value,
        high=q.high_or_value,
        note=q.note,
        unquantified=q.unquantified,
    )


def raw_material_item(material: Material) -> LineItem:
    """Raw-material burden: given directly, or built up from a blend."""
    if not material.is_blend:
        for stage in material.stages:
            if stage.derivation == "" and "raw" in stage.label.lower():
                return _item_from_quantity("raw", stage)
        for stage in material.stages:
            if "raw" in stage.label.lower():
                return _item_from_quantity("raw", stage)
        raise ValueError(f"{material.id}: no raw-material stage and no composition")

    value = sum(c.mass_fraction.value * c.footprint.value for c in material.composition)
    low = sum(c.mass_fraction.value * c.footprint.low_or_value for c in material.composition)
    high = sum(c.mass_fraction.value * c.footprint.high_or_value for c in material.composition)
    tag = weakest(
        [c.footprint.confidence for c in material.composition]
        + [c.mass_fraction.confidence for c in material.composition]
    )
    breakdown = ", ".join(
        f"{c.name} {c.mass_fraction.value:.0%} x {c.footprint.value:.2f} "
        f"[{c.footprint.confidence.marker}]"
        for c in material.composition
    )
    unquantified = tuple(
        f"{c.name}: {driver}"
        for c in material.composition
        for driver in c.footprint.unquantified
    )
    return LineItem(
        kind="raw",
        label="Raw materials (blend)",
        value=value,
        confidence=tag,
        low=low,
        high=high,
        note=f"Mass-weighted from the formulation: {breakdown}.",
        unquantified=unquantified,
    )


def processing_item(material: Material) -> Optional[LineItem]:
    for stage in material.stages:
        if "processing" in stage.label.lower():
            return _item_from_quantity("processing", stage)
    return None


def biogenic_carbon_fraction(material: Material) -> float:
    """kg of biogenic carbon per kg of material."""
    if material.is_blend:
        return sum(
            c.mass_fraction.value * c.carbon_mass_fraction
            for c in material.composition
            if c.biogenic
        )
    return float(material.biogenic_carbon_mass_fraction or 0.0)


def biogenic_credit_item(material: Material, k: Constants) -> Optional[LineItem]:
    """CO2 taken out of the atmosphere and locked into the material.

    Computed from the actual carbon content of the blend, never assumed equal to
    some other biopolymer's.
    """
    c_bio = biogenic_carbon_fraction(material)
    if c_bio <= 0.0:
        return None

    credit = -c_bio * k.co2_per_carbon
    if material.is_blend:
        parts = ", ".join(
            f"{c.name} {c.mass_fraction.value:.0%} at {c.carbon_mass_fraction:.1%} C"
            for c in material.composition
            if c.biogenic
        )
        note = (
            f"Blend is {c_bio:.1%} biogenic carbon by mass ({parts}); "
            f"x {k.co2_per_carbon:.3f} kg CO2 per kg C."
        )
        # Formulation ratios are an input like any other; if they are guesses,
        # so is the credit derived from them.
        tag = weakest(
            [Confidence.DERIVED]
            + [c.mass_fraction.confidence for c in material.composition if c.biogenic]
        )
    else:
        note = f"{c_bio:.1%} biogenic carbon by mass x {k.co2_per_carbon:.3f} kg CO2 per kg C."
        tag = Confidence.DERIVED

    return LineItem(
        kind="biogenic_credit",
        label="Biogenic carbon credit (uptake)",
        value=credit,
        confidence=tag,
        low=credit,
        high=credit,
        note=note,
    )


def eol_items(material: Material, route: EndOfLifeRoute, k: Constants) -> Iterator[LineItem]:
    """The end-of-life burden: the supplied fossil part, then the biogenic return."""
    yield _item_from_quantity("eol_fossil", route.fossil)

    c_bio = biogenic_carbon_fraction(material)
    if c_bio <= 0.0 or route.biogenic_carbon_released_fraction <= 0.0:
        return

    released_c = c_bio * route.biogenic_carbon_released_fraction
    methane_c = released_c * route.methane_share_of_released_carbon
    escaping_c = methane_c * (1.0 - route.methane_capture_rate)

    # Captured methane is flared, so its carbon still leaves as CO2.
    co2 = (released_c - escaping_c) * k.co2_per_carbon
    methane_co2e = escaping_c * k.ch4_per_carbon * k.gwp100_biogenic_methane
    value = co2 + methane_co2e

    retained = c_bio - released_c
    note = (
        f"{route.biogenic_carbon_released_fraction:.0%} of the material's "
        f"{c_bio:.1%} biogenic carbon is released"
    )
    if escaping_c > 0:
        note += (
            f"; {route.methane_share_of_released_carbon:.0%} of that as CH4 with "
            f"{route.methane_capture_rate:.0%} capture, so {methane_co2e:.2f} of the "
            f"{value:.2f} is uncaptured methane at GWP100 {k.gwp100_biogenic_methane:.0f}"
        )
    if retained > 1e-9:
        note += (
            f". The remaining {retained * k.co2_per_carbon:.2f} kg CO2e stays "
            f"sequestered and is left standing as a credit"
        )
    note += "."

    yield LineItem(
        kind="eol_biogenic",
        label="End of life: biogenic carbon released",
        value=value,
        confidence=weakest([Confidence.DERIVED, route.release_confidence]),
        low=value,
        high=value,
        note=note,
    )


def evaluate(material: Material, route: EndOfLifeRoute, k: Constants) -> Result:
    """Full cradle-to-grave account for one material on one disposal route."""
    items: list[LineItem] = [raw_material_item(material)]

    processing = processing_item(material)
    if processing is not None:
        items.append(processing)

    credit = biogenic_credit_item(material, k)
    if credit is not None:
        items.append(credit)

    items.extend(eol_items(material, route, k))
    return Result(material=material, route=route, items=tuple(items))


def evaluate_all(study: Study) -> list[Result]:
    """Every material against every one of its end-of-life routes."""
    return [
        evaluate(material, route, study.constants)
        for material in study.materials
        for route in material.eol_routes
    ]
