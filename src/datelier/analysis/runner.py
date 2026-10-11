"""Explicit worker dispatch through the trusted algorithm catalog."""

from datelier.analysis.algorithms.registry import build_algorithm
from datelier.analysis.types import AnalysisResult, PreparedInput


def run_analysis(prepared: PreparedInput) -> AnalysisResult:
    return build_algorithm(prepared.request.parameters).run(prepared)
