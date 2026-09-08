"""Confidence tagging.

Every number in this model carries a confidence tag, and every tag travels with
its number all the way to the printed output. The rule the whole tool is built
around: a result is only ever as trustworthy as its weakest input, and the
reader must be able to see that without reading a footnote.
"""

from __future__ import annotations

import enum
from typing import Iterable


@enum.unique
class Confidence(enum.Enum):
    """Confidence in an input value, ordered from strongest to weakest.

    ``rank`` drives propagation: combining values yields the weakest tag of the
    inputs. ``marker`` is what gets printed next to the number.

    RECALLED sits below ESTIMATE deliberately. A recollection of the actual
    formulation is more *relevant* than a generic industry figure, but it is
    less *verifiable*, and for a model whose purpose is defensibility it is
    verifiability that has to drive the ranking.
    """

    LITERATURE = ("literature", 0, "LIT", "Literature-backed")
    DERIVED = ("derived", 1, "DER", "Derived by calculation")
    ESTIMATE = ("estimate", 2, "EST", "Industry-typical estimate")
    RECALLED = ("recalled", 3, "RECALLED", "Recalled from memory, not a record")
    PLACEHOLDER = ("placeholder", 4, "PLACEHOLDER", "PLACEHOLDER, needs a source")

    def __init__(self, key: str, rank: int, marker: str, label: str):
        self.key = key
        self.rank = rank
        self.marker = marker
        self.label = label

    @classmethod
    def parse(cls, key: str) -> "Confidence":
        for member in cls:
            if member.key == key:
                return member
        allowed = ", ".join(repr(m.key) for m in cls)
        raise ValueError(f"unknown confidence tag {key!r}; expected one of {allowed}")

    @property
    def is_placeholder(self) -> bool:
        return self is Confidence.PLACEHOLDER

    @property
    def is_unverified(self) -> bool:
        """True for anything that cannot be checked against an external record.

        A recalled figure is not a placeholder -- it is a real statement about
        this specific film rather than a stand-in. But it is no more auditable
        than one, so results built on it must still be marked.
        """
        return self in (Confidence.RECALLED, Confidence.PLACEHOLDER)

    def __str__(self) -> str:
        return self.marker


def weakest(tags: Iterable[Confidence]) -> Confidence:
    """The weakest tag in ``tags`` -- how confidence propagates through a sum.

    Empty input is treated as DERIVED: a total of nothing is an artefact of the
    calculation, not a sourced fact.
    """
    tags = list(tags)
    if not tags:
        return Confidence.DERIVED
    return max(tags, key=lambda t: t.rank)
