import importlib
import warnings

import pytest


@pytest.mark.parametrize(
    "module", ["polars", "numpy", "imgui_bundle", "sklearn", "umap"]
)
def test_runtime_dependency_imports(module: str) -> None:
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always")
        assert importlib.import_module(module) is not None
    # Ordinary UMAP works without its separate TensorFlow-based estimator.
    # Validate that expected upstream notice while rejecting unrelated warnings.
    assert all(
        module == "umap"
        and warning.category is ImportWarning
        and str(warning.message)
        == "Tensorflow not installed; ParametricUMAP will be unavailable"
        for warning in emitted
    )
