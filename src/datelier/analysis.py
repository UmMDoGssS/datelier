"""Explicit estimator boundary. Algorithms are added in verified delivery steps."""

from datelier.analysis_types import AnalysisResult, PreparedInput


def run_analysis(prepared: PreparedInput) -> AnalysisResult:
    raise NotImplementedError(
        f"{prepared.request.algorithm} runner is not implemented yet"
    )
