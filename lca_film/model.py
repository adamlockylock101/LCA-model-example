"""Data structures for the LCA model.

Everything here is a plain container. No numbers are hard-coded: they all come
from ``inputs.toml`` via :mod:`lca_film.config`. The one exception is molar
arithmetic, whose constants also live in the config file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

from .confidence import Confidence, weakest


@dataclass(frozen=True)
class Quantity:
    """A single tagged number: a value, its confidence, its boundary, its source.

    ``boundary`` matters as much as ``confidence``. A perfectly sourced number
    measured on the wrong system boundary produces a confidently wrong
    comparison, which is harder to catch than an obviously missing one.
    """

    label: str
    value: float
    confidence: Confidence
    boundary: str = "unspecified"
    low: Optional[float] = None
    high: Optional[float] = None
    source: str = ""
    note: str = ""
    derivation: str = ""
    overridden_by: str = ""

    @property
    def low_or_value(self) -> float:
        return self.value if self.low is None else self.low

    @property
    def high_or_value(self) -> float:
        return self.value if self.high is None else self.high

    @property
    def tagged(self) -> str:
        """The number as it should always be shown: never without its tag."""
        return f"{self.value:+.2f} [{self.confidence.marker}]"

    @property
    def spread(self) -> float:
        return self.high_or_value - self.low_or_value


@dataclass(frozen=True)
class Component:
    """One constituent of a blended material (alginate, zein, stearic acid).

    Carries both its own footprint and the two numbers needed for the biogenic
    carbon balance: how much of the blend it is, and how much of it is carbon.
    """

    id: str
    name: str
    mass_fraction: Quantity
    footprint: Quantity
    carbon_mass_fraction: float
    biogenic: bool


@dataclass(frozen=True)
class EndOfLifeRoute:
    """One disposal route.

    ``fossil`` is the directly supplied fossil-CO2e burden of the route. For a
    biogenic material the release of the material's own carbon is *not* stored
    here -- it is computed from carbon content at calculation time so that it
    can never fall out of step with the biogenic uptake credit.
    """

    id: str
    label: str
    fossil: Quantity
    biogenic_carbon_released_fraction: float = 0.0
    methane_share_of_released_carbon: float = 0.0
    methane_capture_rate: float = 0.0
    release_confidence: Confidence = Confidence.DERIVED
    release_source: str = ""
    release_note: str = ""


@dataclass(frozen=True)
class QualitativeFlag:
    """An impact with no number attached.

    These exist because the honest answer to some questions is a warning rather
    than a figure. They are printed with the results, not filed away separately,
    precisely because they are invisible in the totals.
    """

    severity: str
    topic: str
    text: str


@dataclass(frozen=True)
class Material:
    id: str
    name: str
    role: str
    summary: str
    stages: Sequence[Quantity] = field(default_factory=tuple)
    composition: Sequence[Component] = field(default_factory=tuple)
    eol_routes: Sequence[EndOfLifeRoute] = field(default_factory=tuple)
    qualitative_flags: Sequence[QualitativeFlag] = field(default_factory=tuple)
    carbon_mass_fraction: Optional[float] = None
    biogenic_carbon_mass_fraction: Optional[float] = None

    @property
    def is_blend(self) -> bool:
        return bool(self.composition)

    @property
    def all_tags(self) -> Confidence:
        tags = [s.confidence for s in self.stages]
        for c in self.composition:
            tags.append(c.footprint.confidence)
            tags.append(c.mass_fraction.confidence)
        return weakest(tags)
