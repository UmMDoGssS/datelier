"""Trusted analysis recipe records; never selected by file-supplied imports."""

from datelier.analysis.algorithms import ALGORITHMS
from datelier.analysis.types import (
    AnalysisRequest,
    Preprocessing,
)

RECORDS = (
    *ALGORITHMS.values(),
    AnalysisRequest,
    Preprocessing,
)
