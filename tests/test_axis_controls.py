import math

import pytest

from datelier.application.axes import AxisState, validate_range
from datelier.workspace.types import WorkspaceViews


@pytest.mark.parametrize("bounds", [(1, 1), (2, 1), (math.nan, 2), (1, math.inf)])
def test_invalid_axis_ranges_are_rejected(bounds: tuple[float, float]) -> None:
    with pytest.raises(ValueError, match="finite"):
        validate_range(bounds)


def test_axis_edits_validate_together_before_publication() -> None:
    axes = AxisState()
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
    axes = AxisState(enabled=(True, False))
    axes.draft = [[0, 40], [2, 2]]
    axes.draft_scales = [0, 2]
    axes.accept()
    assert axes.limits[0] == (0, 40)
    assert axes.limits[1] == (0, 1) and axes.scales[1] == 0


def test_axis_requests_are_once_only_and_edits_start_from_native_pan() -> None:
    axes = AxisState()
    axes.bind("source/x-y", (True, True))
    axes.observe(((-2, 10), (-4, 6)))
    axes.begin_edit()
    assert axes.draft == [[-2, 10], [-4, 6]]
    axes.draft[0] = [1, 10]
    axes.draft_scales[0] = 2
    axes.accept()
    assert axes.take_request() == ((1, 10), (-4, 6))
    assert axes.take_request() is None
    axes.observe(((2, 8), (-3, 5)))
    axes.begin_edit()
    assert axes.draft[0] == [2, 8] and axes.draft_scales[0] == 2
    assert not axes.bind("source/x-y", (True, True))
    assert axes.limits[0] == (2, 8)
    assert axes.bind("other-source/a-b", (True, True))
    assert axes.scales == [0, 0] and not axes.pending


def test_unknown_scale_does_not_publish_valid_axis_before_invalid_axis() -> None:
    axes = AxisState()
    axes.draft = [[2, 20], [1, 5]]
    axes.draft_scales = [2, 7]
    with pytest.raises(ValueError, match="Unknown"):
        axes.accept()
    assert axes.limits == ((0, 1), (0, 1)) and axes.scales == [0, 0]


@pytest.mark.parametrize("height", [-1, 1, math.inf, math.nan])
def test_unusable_saved_plot_heights_fail_validation(height: float) -> None:
    with pytest.raises(ValueError, match="heights"):
        WorkspaceViews(scatter_height=height).validate()
