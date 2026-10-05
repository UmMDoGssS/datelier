import math

import pytest

from datelier.gui_axes import AxisControls, validate_range
from datelier.workspace.types import WorkspaceViews


@pytest.mark.parametrize("bounds", [(1, 1), (2, 1), (math.nan, 2), (1, math.inf)])
def test_invalid_axis_ranges_are_rejected(bounds: tuple[float, float]) -> None:
    with pytest.raises(ValueError, match="finite"):
        validate_range(bounds)


def test_axis_edits_validate_together_before_publication() -> None:
    axes = AxisControls()
    axes.draft = [[2, 20], [5, 1]]
    with pytest.raises(ValueError):
        axes.accept()
    assert axes.limits == ((0, 1), (0, 1)) and not axes.pending
    axes.draft[1] = [1, 5]
    axes.draft_scales = [2, 1]
    axes.accept()
    assert axes.limits == ((2, 20), (1, 5)) and axes.pending
    assert axes.scales == [2, 1]
    axes.draft[0] = [-1, 20]
    with pytest.raises(ValueError, match="positive"):
        axes.accept()
    assert axes.limits == ((2, 20), (1, 5))


def test_categorical_coordinates_cannot_be_replaced_by_numeric_edits() -> None:
    axes = AxisControls(enabled=(True, False))
    axes.draft = [[0, 40], [2, 2]]
    axes.draft_scales = [0, 2]
    axes.accept()
    assert axes.limits[0] == (0, 40)
    assert axes.limits[1] == (0, 1) and axes.scales[1] == 0


@pytest.mark.parametrize("height", [-1, 1, math.inf, math.nan])
def test_unusable_saved_plot_heights_fail_validation(height: float) -> None:
    with pytest.raises(ValueError, match="heights"):
        WorkspaceViews(scatter_height=height).validate()
