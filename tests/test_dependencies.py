import importlib

import pytest


@pytest.mark.parametrize(
    "module", ["polars", "numpy", "imgui_bundle", "sklearn", "umap"]
)
def test_runtime_dependency_imports(module: str) -> None:
    assert importlib.import_module(module) is not None
