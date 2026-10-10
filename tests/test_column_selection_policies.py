"""Domain limits/order remain independent when tools share picker rendering."""

from datelier.application.columns import (
    ColumnChoice,
    MultiSelection,
    ProfileSelectionPolicy,
    SingleSelection,
)

CATALOG = (
    ColumnChoice("a", numeric=True),
    ColumnChoice("text"),
    ColumnChoice("b", numeric=True),
    ColumnChoice("blocked", enabled=False),
)


def test_bounded_features_keep_order_and_reject_ineligible_columns() -> None:
    policy = MultiSelection(limit=2)
    selected = policy.toggle(CATALOG, (), "b")
    selected = policy.toggle(CATALOG, selected, "a")
    assert selected == ("b", "a")
    assert policy.toggle(CATALOG, selected, "text") == selected
    assert policy.toggle(CATALOG, selected, "blocked") == selected
    assert policy.toggle(CATALOG, selected, "missing") == selected
    assert policy.toggle(CATALOG, selected, "a") == ("b",)
    assert policy.bulk(CATALOG) == ("a", "text")
    assert not policy.permits(CATALOG[1], selected)
    assert policy.permits(CATALOG[0], selected)


def test_profiles_allow_numeric_comparison_and_exclusive_other_roles() -> None:
    policy = ProfileSelectionPolicy()
    selected = policy.toggle(CATALOG, ("b",), "a")
    assert selected == ("a", "b")
    assert policy.toggle(CATALOG, selected, "text") == ("text",)
    assert policy.toggle(CATALOG, ("text",), "b") == ("b",)
    assert policy.bulk(CATALOG) == ("a", "b")


def test_supporting_fields_follow_catalog_order_and_single_fields_replace() -> None:
    policy = MultiSelection(catalog_order=True)
    assert policy.toggle(CATALOG, ("b",), "a") == ("a", "b")
    single = SingleSelection()
    assert single.toggle(CATALOG, ("a",), "b") == ("b",)
    assert single.toggle(CATALOG, ("a",), "blocked") == ("a",)
