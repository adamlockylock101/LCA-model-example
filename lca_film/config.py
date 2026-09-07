"""Load and validate ``inputs.toml``.

This is the only bridge between the editable data file and the calculation.
Swapping a value, adding an end-of-life route or re-weighting the blend is done
entirely in the TOML file; nothing below needs to change.

Validation is deliberately strict. A missing confidence tag is an error, not a
default, because an untagged number silently masquerading as a sourced one is
exactly the failure mode this model exists to prevent.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .confidence import Confidence
from .model import (
    Component,
    EndOfLifeRoute,
    Material,
    QualitativeFlag,
    Quantity,
)

DEFAULT_INPUTS = Path(__file__).resolve().parent.parent / "inputs.toml"


@dataclass(frozen=True)
class Constants:
    m_c: float
    m_co2: float
    m_ch4: float
    gwp100_biogenic_methane: float

    @property
    def co2_per_carbon(self) -> float:
        """kg CO2 released per kg of carbon fully oxidised."""
        return self.m_co2 / self.m_c

    @property
    def ch4_per_carbon(self) -> float:
        return self.m_ch4 / self.m_c


@dataclass(frozen=True)
class Study:
    meta: Mapping[str, str]
    constants: Constants
    materials: Sequence[Material]

    def material(self, material_id: str) -> Material:
        for m in self.materials:
            if m.id == material_id:
                return m
        raise KeyError(material_id)


def _require(table: Mapping[str, Any], key: str, where: str) -> Any:
    if key not in table:
        raise ValueError(f"{where}: missing required key {key!r}")
    return table[key]


def _quantity(table: Mapping[str, Any], where: str, *, label: str) -> Quantity:
    confidence = Confidence.parse(str(_require(table, "confidence", where)))
    value = float(_require(table, "value", where))
    low = table.get("low")
    high = table.get("high")
    source = str(table.get("source", "")).strip()
    derivation = str(table.get("derivation", "")).strip()

    # A literature tag without a citation is just an estimate wearing a badge.
    if confidence is Confidence.LITERATURE and not source:
        raise ValueError(f"{where}: confidence='literature' requires a 'source'")
    if confidence is Confidence.DERIVED and not derivation:
        raise ValueError(f"{where}: confidence='derived' requires a 'derivation'")

    low = None if low is None else float(low)
    high = None if high is None else float(high)
    if low is not None and high is not None and low > high:
        raise ValueError(f"{where}: low ({low}) is above high ({high})")
    if low is not None and low > value:
        raise ValueError(f"{where}: value ({value}) is below low ({low})")
    if high is not None and high < value:
        raise ValueError(f"{where}: value ({value}) is above high ({high})")

    return Quantity(
        label=label,
        value=value,
        confidence=confidence,
        low=low,
        high=high,
        source=source,
        note=str(table.get("note", "")).strip(),
        derivation=derivation,
    )


def _component(table: Mapping[str, Any], where: str) -> Component:
    name = str(_require(table, "component", where))
    fraction = Quantity(
        label=f"{name} mass fraction",
        value=float(_require(table, "mass_fraction", where)),
        confidence=Confidence.parse(str(_require(table, "frac_confidence", where))),
        note=str(table.get("frac_note", "")).strip(),
    )
    return Component(
        name=name,
        mass_fraction=fraction,
        footprint=_quantity(table, f"{where} ({name})", label=f"{name} raw material"),
        carbon_mass_fraction=float(_require(table, "carbon_mass_fraction", where)),
        biogenic=bool(_require(table, "biogenic", where)),
    )


def _eol_route(table: Mapping[str, Any], where: str) -> EndOfLifeRoute:
    route_id = str(_require(table, "id", where))
    label = str(_require(table, "label", where))
    fossil = _quantity(table, f"{where} ({route_id})", label=label)

    released = float(table.get("biogenic_carbon_released_fraction", 0.0))
    ch4_share = float(table.get("methane_share_of_released_carbon", 0.0))
    capture = float(table.get("methane_capture_rate", 0.0))
    for name, frac in (
        ("biogenic_carbon_released_fraction", released),
        ("methane_share_of_released_carbon", ch4_share),
        ("methane_capture_rate", capture),
    ):
        if not 0.0 <= frac <= 1.0:
            raise ValueError(f"{where} ({route_id}): {name} must be in [0, 1], got {frac}")

    release_confidence = Confidence.parse(str(table.get("release_confidence", "derived")))
    return EndOfLifeRoute(
        id=route_id,
        label=label,
        fossil=fossil,
        biogenic_carbon_released_fraction=released,
        methane_share_of_released_carbon=ch4_share,
        methane_capture_rate=capture,
        release_confidence=release_confidence,
        release_source=str(table.get("release_source", "")).strip(),
        release_note=str(table.get("release_note", "")).strip(),
    )


def _material(table: Mapping[str, Any]) -> Material:
    material_id = str(_require(table, "id", "material"))
    where = f"material '{material_id}'"

    stages = tuple(
        _quantity(s, f"{where} stage", label=str(_require(s, "label", f"{where} stage")))
        for s in table.get("stages", [])
    )
    composition = tuple(
        _component(c, f"{where} composition") for c in table.get("composition", [])
    )
    eol_routes = tuple(_eol_route(r, f"{where} eol") for r in table.get("eol_routes", []))
    flags = tuple(
        QualitativeFlag(
            severity=str(f.get("severity", "medium")),
            topic=str(_require(f, "topic", f"{where} flag")),
            text=str(_require(f, "text", f"{where} flag")),
        )
        for f in table.get("qualitative_flags", [])
    )

    if not eol_routes:
        raise ValueError(f"{where}: at least one end-of-life route is required")

    if composition:
        total = sum(c.mass_fraction.value for c in composition)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"{where}: composition mass fractions sum to {total:.4f}, expected 1.0"
            )

    return Material(
        id=material_id,
        name=str(_require(table, "name", where)),
        role=str(table.get("role", "")),
        summary=str(table.get("summary", "")),
        stages=stages,
        composition=composition,
        eol_routes=eol_routes,
        qualitative_flags=flags,
        carbon_mass_fraction=table.get("carbon_mass_fraction"),
        biogenic_carbon_mass_fraction=table.get("biogenic_carbon_mass_fraction"),
    )


def load_study(path: Path | str | None = None) -> Study:
    """Read the input file and return a validated :class:`Study`."""
    path = Path(path) if path is not None else DEFAULT_INPUTS
    with open(path, "rb") as fh:
        raw = tomllib.load(fh)

    constants = Constants(**raw["constants"])
    materials = tuple(_material(m) for m in raw.get("materials", []))
    if not materials:
        raise ValueError(f"{path}: no materials defined")

    return Study(meta=raw.get("meta", {}), constants=constants, materials=materials)
