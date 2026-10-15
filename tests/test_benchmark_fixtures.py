from scripts.support.tables import make_table


def test_fixture_is_deterministic_mixed_and_identified() -> None:
    table = make_table(100, 10)
    assert table.equals(make_table(100, 10))
    assert table.shape == (100, 12)
    assert table["row_id"].n_unique() == 100
    assert table["feature_9"].null_count() == 6
    assert table["category"].n_unique() == 3
