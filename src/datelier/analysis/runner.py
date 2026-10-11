"""Explicit worker dispatch through the trusted algorithm catalog."""

from datelier.analysis.types import AnalysisResult, PreparedInput


def run_analysis(prepared: PreparedInput) -> AnalysisResult:
    return prepared.request.parameters.fit(prepared)
