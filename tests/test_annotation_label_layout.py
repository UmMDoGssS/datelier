"""Screen labels avoid overlap without modifying the underlying box geometry."""

from datelier.inspection.annotations.label_layout import LabelLayout
from datelier.inspection.annotations.overlay import OverlaySettings
from datelier.workspace.codec import decode_record, encode


def test_labels_cross_cell_boundaries_and_allow_touching_neighbors() -> None:
    layout = LabelLayout()
    assert layout.reserve((60, 12, 100, 25))
    assert not layout.reserve((90, 20, 120, 30))
    assert layout.reserve((100, 12, 140, 25))
    assert layout.reserve((60, 25, 100, 38))
    assert not layout.reserve((60, 12, 100, 25))
    assert layout.reserve((-20, -10, 0, 0))
    assert not layout.reserve((10, 0, 10, 10))


def test_failed_label_reservations_do_not_hide_later_clear_labels() -> None:
    layout = LabelLayout()
    assert layout.reserve((0, 0, 50, 12))
    assert not layout.reserve((40, 0, 90, 12))
    assert layout.reserve((50, 0, 90, 12))


def test_overlap_choice_roundtrips_with_safe_legacy_default() -> None:
    settings = OverlaySettings(overlapping_labels=True)
    assert decode_record(OverlaySettings, encode(settings)) == settings
    raw = encode(settings)
    assert isinstance(raw, dict)
    raw.pop("overlapping_labels")
    assert not decode_record(OverlaySettings, raw).overlapping_labels
