"""Exact shared-tokenizer overlays, incompatible results and source identity."""

from dataclasses import replace
from pathlib import Path
from threading import Event
from time import monotonic, sleep
from unittest.mock import patch

import numpy as np
import polars as pl
import pytest

from datelier.core.jobs import SharedWorkers
from datelier.inspection.text.comparisons.jobs import TextComparisonJobs
from datelier.inspection.text.comparisons.prepare import (
    compare_profiles,
    prepare_comparison,
    select_length_bin,
)
from datelier.inspection.text.comparisons.settings import (
    TextComparisonSettings,
    TextComparisonSource,
    TextScale,
)
from datelier.inspection.text.comparisons.types import (
    PreparedTextComparison,
    TextComparisonInput,
)
from datelier.inspection.text.corpus import TextProgress
from datelier.inspection.text.types import (
    CorpusMode,
    Normalization,
    TextScope,
    TextSource,
    TokenMode,
    TokenSettings,
)
from datelier.io.importing import load_file
from datelier.workspace.recipes.codec import decode_record, encode
from datelier.workspace.sessions import SessionFile, SessionWorkspace


def inputs(root: Path) -> tuple[TextComparisonInput, ...]:
    result = []
    for name, texts in (
        ("a", ["A a", "b", "", None]),
        ("b", ["a b b", "c c c c", "b"]),
    ):
        path = root / f"{name}.csv"
        pl.DataFrame({"text": texts}).write_csv(path)
        dataset = load_file(path).dataset
        source = TextComparisonSource(
            name, "text", TextSource.INLINE, scope=TextScope(CorpusMode.COLLECTION)
        )
        result.append(TextComparisonInput(source, dataset, name))
    return tuple(result)


def prepare(
    items: tuple[TextComparisonInput, ...], *, scale: TextScale = TextScale.COUNT
) -> PreparedTextComparison:
    settings = TextComparisonSettings(
        tuple(i.source for i in items),
        TokenSettings(lowercase=True),
        bins=4,
        scale=scale,
    )
    return prepare_comparison(items, settings, Event(), TextProgress())


def test_exact_union_shared_edges_density_and_namespaced_selection(
    tmp_path: Path,
) -> None:
    items = inputs(tmp_path)
    result = prepare(items)
    assert [p.tokens for p in result.profiles] == [3, 8]
    assert result.frequencies.rows() == [
        ("b", None, 1, 1, 3, 2),
        ("c", None, 0, 0, 4, 1),
        ("a", None, 2, 1, 1, 1),
    ]
    assert result.frequency_labels == ("'b'", "'c'", "'a'")
    assert [sum(v) for v in result.lengths] == [3, 3]
    assert result.edges.tolist() == [0, 1, 2, 3, 4]
    density = prepare(items, scale=TextScale.DENSITY)
    assert all(
        np.sum(v) * (density.edges[1] - density.edges[0]) == pytest.approx(1)
        for v in density.lengths
    )
    assert density.token_frequencies[0].tolist() == pytest.approx([1 / 3, 0, 2 / 3])
    assert density.document_frequencies[1].tolist() == pytest.approx(
        [2 / 3, 1 / 3, 1 / 3]
    )
    selection = select_length_bin(result, 1, 3, items[1].dataset)
    assert selection.origin.file_id == "b" and selection.row_ids == (0, 1)
    assert selection.matches == 2 and selection.first_position == 0
    # Source row 0 also exists in a; it never becomes the same selected record.
    assert select_length_bin(result, 0, 2, items[0].dataset).row_ids == (0,)
    assert result.retained_bytes > 0


@pytest.mark.parametrize(
    "tokens",
    [
        TokenSettings(),
        TokenSettings(TokenMode.CHARACTER, lowercase=True),
        TokenSettings(normalization=Normalization.NFKC, lowercase=True),
        TokenSettings(lowercase=True, count_special_tokens=True),
    ],
)
def test_incompatible_tokenizer_never_overlays_as_equivalent(
    tmp_path: Path, tokens: TokenSettings
) -> None:
    result = prepare(inputs(tmp_path))
    incompatible = replace(
        result.profiles[1], settings=replace(result.profiles[1].settings, tokens=tokens)
    )
    with pytest.raises(ValueError, match="Incompatible tokenizers"):
        compare_profiles(
            (result.profiles[0], incompatible), result.labels, result.settings
        )


def test_scopes_empty_vocabulary_and_workspace_recipe(tmp_path: Path) -> None:
    items = inputs(tmp_path)
    selected = replace(
        items[0],
        source=replace(items[0].source, scope=TextScope(CorpusMode.SELECTION)),
        selection=(1,),
    )
    empty = replace(
        items[1],
        source=replace(items[1].source, scope=TextScope(CorpusMode.RANGE, 100, 5)),
    )
    result = prepare((selected, empty))
    assert result.profiles[0].records["source_row_id"].to_list() == [1]
    assert result.profiles[1].documents == 0 and sum(result.lengths[1]) == 0
    assert result.token_frequencies[1].tolist() == [0]
    zero = prepare((replace(selected, selection=()), empty))
    assert zero.frequencies.height == 0 and zero.frequency_labels == ()
    session = SessionWorkspace(
        (SessionFile("a"), SessionFile("b")), "a", text_comparisons=(result.settings,)
    )
    session.validate()
    restored = decode_record(SessionWorkspace, encode(session))
    assert restored == session
    restored.validate()
    with pytest.raises(ValueError, match="closed file"):
        replace(session, files=(SessionFile("a"),)).validate()


def test_explicit_jobs_invalidation_missing_sources_and_late_close(
    tmp_path: Path,
) -> None:
    items = inputs(tmp_path)
    settings = TextComparisonSettings(tuple(i.source for i in items))
    workers = SharedWorkers()
    jobs = TextComparisonJobs(workers)
    release, started = Event(), Event()
    try:
        jobs.bind(settings, items)
        assert jobs.started == 0 and jobs.active is None
        jobs.request()
        deadline = monotonic() + 5
        while jobs.busy and monotonic() < deadline:
            jobs.bind(settings, items)
            jobs.poll()
            sleep(0.001)
        assert jobs.active and not jobs.busy
        result = jobs.active
        jobs.request_selection(result, 1, 23, items[1].dataset)
        deadline = monotonic() + 5
        selection = None
        while selection is None and monotonic() < deadline:
            selection = jobs.poll_selection(
                {i.source.file_id: i.dataset for i in items}
            )
            sleep(0.001)
        assert (
            selection and selection.origin.file_id == "b" and selection.row_ids == (1,)
        )
        changed = (
            items[0],
            replace(items[1], dataset=items[1].dataset.with_role("text", None)),
        )
        jobs.bind(settings, changed)
        assert jobs.active is None and jobs.started == 1
        jobs.bind(settings, items[:1])
        with pytest.raises(ValueError, match="available"):
            jobs.request()
        jobs.bind(settings, items)

        def slow(*args: object) -> PreparedTextComparison:
            started.set()
            assert release.wait(3)
            return prepare_comparison(items, settings, Event(), TextProgress())

        with patch(
            "datelier.inspection.text.comparisons.jobs.prepare_comparison",
            side_effect=slow,
        ):
            jobs.request()
        assert started.wait(3)
        pending = jobs._future
        assert pending
        jobs.close()
        release.set()
        pending.result(3)
        jobs.bind(settings, items)
        assert jobs.active is None
    finally:
        release.set()
        jobs.close()
        workers.shutdown()


def test_local_tokenizer_digest_controls_compatibility(tmp_path: Path) -> None:
    from shutil import copyfile

    from tokenizers import Tokenizer, models

    from datelier.inspection.text.tokenization import import_tokenizer

    items = inputs(tmp_path)
    first, copied, other = (
        tmp_path / name for name in ("first.json", "copy.json", "other.json")
    )
    Tokenizer(models.BPE({"a": 0, "b": 1, "c": 2, "A": 3}, [])).save(str(first))
    copyfile(first, copied)
    Tokenizer(models.BPE({"a": 1, "b": 0, "c": 2, "A": 3}, [])).save(str(other))
    tokens = TokenSettings(TokenMode.BPE, artifact=import_tokenizer(first))
    recipe = TextComparisonSettings(tuple(i.source for i in items), tokens)
    result = prepare_comparison(items, recipe, Event(), TextProgress())
    same = replace(
        result.profiles[1],
        settings=replace(
            result.profiles[1].settings,
            tokens=replace(tokens, artifact=import_tokenizer(copied)),
        ),
    )
    assert compare_profiles(
        (result.profiles[0], same), result.labels, recipe
    ).frequencies.equals(result.frequencies)
    changed = replace(
        same,
        settings=replace(
            same.settings, tokens=replace(tokens, artifact=import_tokenizer(other))
        ),
    )
    with pytest.raises(ValueError, match="Incompatible tokenizers"):
        compare_profiles((result.profiles[0], changed), result.labels, recipe)
