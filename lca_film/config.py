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

from .boundary import BoundaryIssue, is_comparable
from .confidence import Confidence
from .model import (
    Component,
    EndOfLifeRoute,
    Material,
    QualitativeFlag,
    Quantity,
    ScopeVariant,
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
    scenario: str = "default"
    scenario_label: str = "As sourced"
    scenario_description: str = ""

    def material(self, material_id: str) -> Material:
        for m in self.materials:
            if m.id == material_id:
                return m
        raise KeyError(material_id)

    @property
    def target_boundary(self) -> str:
        return str(self.meta.get("target_boundary", "factory_gate"))

    def boundary_issues(self) -> list[BoundaryIssue]:
        """Every raw-material input not measured on the study's target boundary."""
        target = self.target_boundary
        issues: list[BoundaryIssue] = []
        for material in self.materials:
            quantities = list(material.stages) + [
                c.footprint for c in material.composition
            ]
            for q in quantities:
                if not is_comparable(q.boundary, target):
                    issues.append(
                        BoundaryIssue(
                            material=material.name,
                            input_label=q.label,
                            found=q.boundary,
                            target=target,
                        )
                    )
        return issues


def _require(table: Mapping[str, Any], key: str, where: str) -> Any:
    if key not in table:
        raise ValueError(f"{where}: missing required key {key!r}")
    return table[key]


def _scope_variant(table: Mapping[str, Any], where: str) -> ScopeVariant:
    """Parse an alternative measurement, refusing one that hides its scope.

    A variant declared non-comparable must say WHY. Otherwise the next reader
    has no way to tell a genuine alternative from a number someone wanted out
    of the range for the wrong reasons.
    """
    variant_id = str(_require(table, "id", where))
    where = f"{where} variant '{variant_id}'"
    comparable = bool(table.get("comparable", False))
    why = str(table.get("why_not_comparable", "")).strip()
    if not comparable and not why:
        raise ValueError(
            f"{where}: comparable=false requires 'why_not_comparable' -- state "
            f"what this measures instead"
        )
    confidence = Confidence.parse(str(_require(table, "confidence", where)))
    if confidence is Confidence.LITERATURE and not str(table.get("source", "")).strip():
        raise ValueError(f"{where}: confidence='literature' requires a 'source'")

    return ScopeVariant(
        id=variant_id,
        label=str(_require(table, "label", where)),
        value=float(_require(table, "value", where)),
        confidence=confidence,
        product=str(table.get("product", "")).strip(),
        feedstock=str(table.get("feedstock", "")).strip(),
        includes=str(table.get("includes", "")).strip(),
        excludes=str(table.get("excludes", "")).strip(),
        comparable=comparable,
        why_not_comparable=why,
        low=None if table.get("low") is None else float(table["low"]),
        high=None if table.get("high") is None else float(table["high"]),
        source=str(table.get("source", "")).strip(),
        note=str(table.get("note", "")).strip(),
    )


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

    variants = tuple(
        _scope_variant(v, where) for v in table.get("scope_variants", [])
    )
    # A non-comparable variant must never have leaked into the range.
    for variant in variants:
        if variant.comparable:
            continue
        if low is not None and abs(low - variant.value) < 1e-9:
            raise ValueError(
                f"{where}: low bound {low} is scope variant '{variant.id}', which "
                f"is declared not comparable -- it measures something else and "
                f"cannot bound this quantity"
            )
        if high is not None and abs(high - variant.value) < 1e-9:
            raise ValueError(
                f"{where}: high bound {high} is scope variant '{variant.id}', "
                f"which is declared not comparable"
            )

    return Quantity(
        label=label,
        value=value,
        confidence=confidence,
        boundary=str(table.get("boundary", "unspecified")),
        low=low,
        high=high,
        source=source,
        note=str(table.get("note", "")).strip(),
        derivation=derivation,
        overridden_by=str(table.get("overridden_by", "")).strip(),
        unquantified=tuple(str(u) for u in table.get("unquantified", [])),
        scope_variants=variants,
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
        id=str(table.get("id", name.lower().replace(" ", "_"))),
        name=name,
        dry_mass_g=(
            None if table.get("dry_mass_g") is None else float(table["dry_mass_g"])
        ),
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


def _normalise_dry_masses(table: Mapping[str, Any], where: str) -> None:
    """Turn a recalled recipe in grams into mass fractions, in place.

    Recording the recipe as it was actually given -- 0.8 g, 0.3 g, 0.3 g -- and
    normalising here keeps the primary record intact and avoids hand-rounded
    percentages that fail the sum-to-one check or silently shift the blend.
    Solvents are excluded by construction: only dry-film components are listed.
    """
    entries = table.get("composition", [])
    with_mass = [e for e in entries if "dry_mass_g" in e]
    if not with_mass:
        return
    if len(with_mass) != len(entries):
        raise ValueError(
            f"{where}: composition mixes 'dry_mass_g' and 'mass_fraction'; "
            f"use one basis for the whole blend"
        )
    total = sum(float(e["dry_mass_g"]) for e in entries)
    if total <= 0:
        raise ValueError(f"{where}: dry masses sum to {total}, expected a positive mass")
    for entry in entries:
        entry["mass_fraction"] = float(entry["dry_mass_g"]) / total


def _material(table: Mapping[str, Any]) -> Material:
    material_id = str(_require(table, "id", "material"))
    where = f"material '{material_id}'"
    _normalise_dry_masses(table, where)

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


def _apply_overrides(
    raw: dict, overrides: Sequence[Mapping[str, Any]], label: str
) -> None:
    """Rewrite raw input tables in place before they are validated.

    Overrides are applied to the raw TOML rather than to built objects so that
    an overridden value goes through exactly the same validation as an authored
    one. A scenario cannot smuggle in a literature tag with no source.
    """
    for override in overrides:
        path = str(_require(override, "path", f"scenario '{label}'"))
        target = _resolve_path(raw, path, label)

        # `variant = "<id>"` swaps in a declared scope variant wholesale, so the
        # scenario cannot drift from the variant it claims to be using.
        variant_id = override.get("variant")
        if variant_id is not None:
            source_variant = next(
                (
                    v
                    for v in target.get("scope_variants", [])
                    if v.get("id") == variant_id
                ),
                None,
            )
            if source_variant is None:
                known = ", ".join(
                    repr(v.get("id")) for v in target.get("scope_variants", [])
                ) or "none declared"
                raise ValueError(
                    f"scenario '{label}': no scope variant {variant_id!r} on "
                    f"{path!r}; available: {known}"
                )
            for key in ("value", "low", "high", "confidence", "source", "note"):
                if key in source_variant:
                    target[key] = source_variant[key]
            target["note"] = (
                f"SCOPE VARIANT IN USE ({variant_id}). "
                f"{source_variant.get('why_not_comparable', '')} "
                f"{source_variant.get('note', '')}".strip()
            )
            # The variant is now the value, so it can no longer bound itself.
            target["scope_variants"] = []

        for key, value in override.items():
            if key in ("path", "variant"):
                continue
            target[key] = value
        # Clear any stale bound that the override did not restate, so a new
        # central value can never sit outside a leftover range.
        if "value" in override:
            if "low" not in override:
                target.pop("low", None)
            if "high" not in override:
                target.pop("high", None)
        target["overridden_by"] = label


def _resolve_path(raw: dict, path: str, label: str) -> dict:
    """Resolve '<material>/<kind>/<id>' to the raw table it names."""
    try:
        material_id, kind, item_id = path.split("/")
    except ValueError:
        raise ValueError(
            f"scenario '{label}': override path {path!r} must be "
            f"'<material_id>/<stage|component|eol>/<id>'"
        ) from None

    key = {"stage": "stages", "component": "composition", "eol": "eol_routes"}.get(kind)
    if key is None:
        raise ValueError(
            f"scenario '{label}': unknown path kind {kind!r} in {path!r}; "
            f"expected 'stage', 'component' or 'eol'"
        )

    for material in raw.get("materials", []):
        if material.get("id") != material_id:
            continue
        for entry in material.get(key, []):
            entry_id = entry.get("id") or entry.get("component", "")
            if entry_id == item_id:
                return entry
        raise ValueError(
            f"scenario '{label}': no {kind} {item_id!r} on material {material_id!r}"
        )
    raise ValueError(f"scenario '{label}': no material {material_id!r}")


def load_study(
    path: Path | str | None = None,
    scenario: str = "default",
    overrides: Sequence[Mapping[str, Any]] = (),
) -> Study:
    """Read the input file, apply a scenario and any ad-hoc overrides, validate.

    ``overrides`` are applied after the named scenario, so a ``--set`` on the
    command line beats the scenario it is layered on top of.
    """
    path = Path(path) if path is not None else DEFAULT_INPUTS
    with open(path, "rb") as fh:
        raw = tomllib.load(fh)

    scenarios = raw.get("scenarios", {})
    if scenario not in scenarios and scenario != "default":
        known = ", ".join(sorted(scenarios)) or "none defined"
        raise ValueError(f"unknown scenario {scenario!r}; available: {known}")

    spec = scenarios.get(scenario, {})
    _apply_overrides(raw, spec.get("overrides", []), scenario)
    if overrides:
        _apply_overrides(raw, overrides, "--set")

    constants = Constants(**raw["constants"])
    materials = tuple(_material(m) for m in raw.get("materials", []))
    if not materials:
        raise ValueError(f"{path}: no materials defined")

    return Study(
        meta=raw.get("meta", {}),
        constants=constants,
        materials=materials,
        scenario=scenario,
        scenario_label=str(spec.get("label", scenario)),
        scenario_description=str(spec.get("description", "")),
    )


def list_scenarios(path: Path | str | None = None) -> dict[str, dict]:
    """Scenario names, labels and descriptions, without applying any."""
    path = Path(path) if path is not None else DEFAULT_INPUTS
    with open(path, "rb") as fh:
        raw = tomllib.load(fh)
    return raw.get("scenarios", {})
