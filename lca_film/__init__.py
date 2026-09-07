"""Pluggable cradle-to-grave LCA model for a sanitary product anti-leak film.

Compares PVA (incumbent), LDPE (reference) and an alginate/zein/stearic acid
biomaterial film. All input data lives in ``inputs.toml``; this package only
loads, calculates and reports.
"""

from .calculate import Result, evaluate, evaluate_all
from .config import Study, load_study
from .confidence import Confidence

__all__ = [
    "Confidence",
    "Result",
    "Study",
    "evaluate",
    "evaluate_all",
    "load_study",
]
