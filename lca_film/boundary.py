"""System-boundary tracking.

A number can be impeccably sourced and still wrong for the comparison it is put
into, if it was measured to a different system boundary. That failure is quiet:
nothing looks broken, the total is just wrong. So the boundary of every input is
recorded and checked against the study's target, and any mismatch is reported
next to the results rather than left to the reader to notice.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Boundaries that are not raw-material acquisition and so are never compared
#: against the study target.
NON_MATERIAL = frozenset({"process", "eol"})

DESCRIPTIONS = {
    "factory_gate": (
        "Cradle to factory gate: unpacked material at production site out. "
        "No packaging, storage, retail transport or land-use change."
    ),
    "retail_shelf": (
        "Cradle to retail shelf: includes packaging, storage, retail transport "
        "AND land-use change. WIDER than factory gate, so biased HIGH."
    ),
    "process": "Gate-to-gate conversion step.",
    "eol": "End of life.",
    "unspecified": "Boundary not recorded.",
}


@dataclass(frozen=True)
class BoundaryIssue:
    """One input measured on a boundary other than the study's target."""

    material: str
    input_label: str
    found: str
    target: str

    @property
    def direction(self) -> str:
        if self.found == "retail_shelf" and self.target == "factory_gate":
            return "OVERSTATES this material"
        if self.found == "factory_gate" and self.target == "retail_shelf":
            return "UNDERSTATES this material"
        return "direction of bias unknown"

    def describe(self) -> str:
        return (
            f"{self.material}: '{self.input_label}' is on the {self.found!r} "
            f"boundary, study target is {self.target!r} -- {self.direction}."
        )


def is_comparable(found: str, target: str) -> bool:
    return found in NON_MATERIAL or found == target
