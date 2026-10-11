"""Public schema behavior, independent drafts and legacy recipe compatibility."""

import json
import subprocess
import sys
from dataclasses import replace
from typing import cast

import pytest

from datelier.analysis.algorithms.registry import ALGORITHMS
from datelier.analysis.parameters import MeanShiftParameters
from datelier.analysis.types import Algorithm, AnalysisRequest, TSNEParameters
from datelier.application.analysis_settings import AnalysisSettings
from datelier.workspace.codec import decode_record, encode


def test_catalog_import_and_default_validation_never_import_estimators() -> None:
    process = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, json; "
            "from datelier.analysis.algorithms.registry import ALGORITHMS; "
            "[builder().validate() for builder in ALGORITHMS.values()]; "
            "print(json.dumps(sorted(set(sys.modules) & "
            "{'sklearn', 'umap', 'numba', 'imgui_bundle'})))",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    assert json.loads(process.stdout) == []


@pytest.mark.parametrize("algorithm", tuple(Algorithm))
def test_schema_updates_round_trip_as_typed_workspace_recipes(
    algorithm: Algorithm,
) -> None:
    controls = AnalysisSettings(features=["y", "x"])
    builder = ALGORITHMS[algorithm]()
    for descriptor in builder.schema:
        if descriptor.choices:
            value = descriptor.choices[-1]
        elif descriptor.automatic:
            value = descriptor.manual_default
        elif type(descriptor.default) is bool:
            value = not descriptor.default
        else:
            value = descriptor.default
        controls.update(algorithm, descriptor.name, value)
    request = controls.request(algorithm)
    request.validate()
    decoded = decode_record(AnalysisRequest, encode(request))
    assert decoded == request
    restored = AnalysisSettings(features=list(decoded.features))
    restored.restore(decoded)
    assert restored.request(algorithm) == request
    untouched = AnalysisSettings(features=["y", "x"])
    for other in Algorithm:
        if other != algorithm:
            assert controls.request(other) == untouched.request(other)


def test_conditional_parameters_share_gui_visibility_and_validation() -> None:
    automatic = MeanShiftParameters(bandwidth=-5)
    manual = MeanShiftParameters(automatic_bandwidth=False, bandwidth=-5)
    assert {field.name for field in automatic.schema if field.visible(automatic)} >= {
        "quantile",
        "automatic_bandwidth",
    }
    assert not next(f for f in automatic.schema if f.name == "bandwidth").visible(
        automatic
    )
    automatic.validate()
    with pytest.raises(ValueError, match="Bandwidth"):
        manual.validate()


@pytest.mark.parametrize(
    "parameters",
    [
        TSNEParameters(learning_rate="unsupported"),
        TSNEParameters(learning_rate=float("nan")),
        TSNEParameters(perplexity=cast(float, False)),
        TSNEParameters(iterations=cast(int, 250.5)),
        TSNEParameters(initialization="unsupported"),
    ],
)
def test_schema_rejects_bad_values_before_execution(parameters: TSNEParameters) -> None:
    with pytest.raises(ValueError):
        AnalysisRequest(("x", "y"), parameters).validate()


def test_legacy_tsne_recipe_retains_auto_or_numeric_rate() -> None:
    for rate in ("auto", 55.0):
        legacy = {
            "kind": "AnalysisRequest",
            "features": ["x", "y"],
            "parameters": {
                "kind": "TSNEParameters",
                "perplexity": 4,
                "iterations": 300,
                "learning_rate": rate,
                "initialization": "random",
            },
        }
        request = decode_record(AnalysisRequest, legacy)
        assert request.parameters == TSNEParameters(4, 300, rate, "random")
        controls = AnalysisSettings(features=list(request.features))
        controls.restore(request)
        assert controls.request(Algorithm.TSNE) == request
        assert controls.matches_result(request)
        assert isinstance(request.parameters, TSNEParameters)
        controls.parameters[Algorithm.TSNE] = replace(request.parameters, perplexity=6)
        assert not controls.matches_result(request)
