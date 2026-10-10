"""Explicit class and row edits preserve provenance and require revalidation."""

from dataclasses import replace

import pytest

from datelier.application.annotations.recipes import class_names, confirm_mapping
from datelier.inspection.annotations.settings import (
    AnnotationSource,
    ImageAssociationMapping,
)
from datelier.inspection.annotations.types import AnnotationClass


def test_class_names_allow_sparse_ids_spaces_and_empty_numeric_mapping() -> None:
    assert class_names("0 person\n\n7 traffic light\n") == (
        AnnotationClass(0, "person"),
        AnnotationClass(7, "traffic light"),
    )
    assert class_names("\n") == ()


@pytest.mark.parametrize("text", ["cat", "cat name", "-1 cat", "1 cat\n1 dog"])
def test_invalid_class_edits_do_not_produce_a_partial_recipe(text: str) -> None:
    with pytest.raises(ValueError, match="Line"):
        class_names(text)


def test_reconfirming_one_mapping_retires_only_its_old_pin() -> None:
    source = AnnotationSource(
        "truth",
        "labels",
        mappings=(
            ImageAssociationMapping("one", 0, "old reference"),
            ImageAssociationMapping("two", 2, "unchanged reference"),
        ),
    )
    confirmed = confirm_mapping(source, "one", 3)
    assert confirmed == replace(
        source, mappings=(source.mappings[1], ImageAssociationMapping("one", 3))
    )
    assert source.mappings[0].expected_key == "old reference"
    with pytest.raises(ValueError):
        confirm_mapping(source, "", 0)
    with pytest.raises(ValueError):
        confirm_mapping(source, "one", -1)
