import json
from dataclasses import replace
from pathlib import Path
from threading import Event
from time import monotonic, sleep

import polars as pl
import pytest

from datelier.application.exploration import ProfileFamily
from datelier.application.media.records import RecordKind
from datelier.application.sessions import EditorController
from datelier.core import ColumnRole, Dataset, SourceReference
from datelier.inspection.profiles import ProfileSelection
from datelier.inspection.profiles.preview import ProfileRequest, prepare_profile_group
from datelier.inspection.references import ReferenceSettings
from datelier.inspection.text.comparisons import (
    TextComparisonSettings,
    TextComparisonSource,
)
from datelier.inspection.text.comparisons.prepare import (
    compare_profiles,
    select_length_bin,
)
from datelier.inspection.text.jobs import TextJobs
from datelier.inspection.text.profiles import TextProfile, calculate_profile
from datelier.inspection.text.profiles.corpus import TextProgress
from datelier.inspection.text.tokenizers.prepare import prepare_document
from datelier.inspection.text.tokenizers.training import train_tokenizer
from datelier.inspection.text.types import (
    CorpusMode,
    TextScope,
    TextSettings,
    TextSource,
    TrainingSettings,
)
from datelier.io.importing import load_file
from datelier.pipeline import Pipeline, SetColumnRole, Sort
from datelier.plotting.distributions import DistributionSettings
from datelier.workspace.recipes.codec import decode_record, encode


def data(tmp_path: Path) -> Dataset:
    path = tmp_path / "source.json"
    path.write_text(
        json.dumps(
            [
                {"id": 0, "text": [["a a b", ""], None, [None, "c"]]},
                {"id": 1, "text": [["b c"]]},
                {"id": 2, "text": []},
                {"id": 3, "text": None},
                {"id": 4, "text": [["a"]]},
            ]
        )
    )
    return (
        Pipeline.start(load_file(path).dataset)
        .apply(SetColumnRole("text", ColumnRole.LIST_TEXT))
        .current
    )


def settings() -> TextSettings:
    return TextSettings("text", scope=TextScope(CorpusMode.COLLECTION))


def profile(
    dataset: Dataset, value: TextSettings | None = None, selection: tuple[int, ...] = ()
) -> TextProfile:
    return calculate_profile(
        dataset,
        "file",
        value or settings(),
        selection,
        ReferenceSettings(),
        None,
        Event(),
        TextProgress(),
    )


def test_list_text_totals_are_element_weighted_without_phantom_documents(
    tmp_path: Path,
) -> None:
    dataset = data(tmp_path)
    result = profile(dataset)
    assert result.is_list
    assert (
        result.requested_records,
        result.documents,
        result.nulls,
        result.empty,
        result.tokens,
    ) == (5, 5, 1, 1, 7)
    assert result.records["source_row_id"].to_list() == [0, 0, 0, 0, 1, 4]
    assert result.records["element_path"].to_list() == [
        [0, 0],
        [0, 1],
        [2, 0],
        [2, 1],
        [0, 0],
        [0, 0],
    ]
    assert result.frequencies.select("piece", "tokens", "documents").rows() == [
        ("a", 3, 2),
        ("b", 2, 2),
        ("c", 2, 2),
    ]
    assert result.token_lengths.count == 5 and result.token_lengths.mean == 1.4
    assert dataset.row_ids.to_list() == [0, 1, 2, 3, 4]
    selected = ProfileSelection(("text",))
    selected.bind(dataset)
    assert selected.text_column() == "text"
    editor = EditorController()
    try:
        file = editor.active
        file.open(dataset.source.path)
        deadline = monotonic() + 3
        while file.inspection is None and monotonic() < deadline:
            editor.poll()
            sleep(0.001)
        assert file.inspection
        file.profiles.choose(("text",))
        file.profiles.text = True
        file.records.settings = replace(
            file.records.settings, primary="text", text_elements=True
        )
        editor.poll()
        assert file.profiles.family == ProfileFamily.TEXT
        assert file.records.current_kind() == RecordKind.TEXT
        assert file.text.jobs.settings.column == "text" and file.text.record_list
        assert file.text.corpus.profile is None and not file.text.corpus.busy
    finally:
        editor.close()


def test_sorted_scopes_and_selected_element_keep_exact_origin_and_token_spans(
    tmp_path: Path,
) -> None:
    dataset = data(tmp_path)
    reversed_data = Pipeline.start(dataset).apply(Sort(("id",), True)).current
    result = profile(
        reversed_data,
        replace(settings(), scope=TextScope(CorpusMode.SELECTION)),
        (0, 4),
    )
    assert result.requested_records == 2 and result.records[
        "source_row_id"
    ].to_list() == [4, 0, 0, 0, 0]
    prepared = prepare_document(
        reversed_data,
        "file",
        replace(settings(), position=4, element_index=3),
        ReferenceSettings(),
        None,
    )
    assert prepared.document.text == "c" and prepared.document.origin.row_id == 0
    assert prepared.document.origin.element_path == (2, 1)
    assert [(token.start, token.end, token.piece) for token in prepared.tokens] == [
        (0, 1, "c")
    ]
    empty = prepare_document(
        dataset, "file", replace(settings(), position=2), ReferenceSettings(), None
    )
    assert empty.count == 0 and "no text elements" in empty.document.diagnostic
    with pytest.raises(ValueError, match="4 text elements"):
        prepare_document(
            dataset,
            "file",
            replace(settings(), element_index=10),
            ReferenceSettings(),
            None,
        )
    with pytest.raises(ValueError, match="inline"):
        profile(dataset, replace(settings(), source=TextSource.EXTERNAL))
    stop = Event()
    stop.set()
    with pytest.raises(ValueError, match="abandoned"):
        calculate_profile(
            dataset,
            "file",
            settings(),
            (),
            ReferenceSettings(),
            None,
            stop,
            TextProgress(),
        )


def test_element_navigation_invalidates_only_document_and_workspace_defaults_migrate(
    tmp_path: Path,
) -> None:
    dataset = data(tmp_path)
    jobs = TextJobs()
    try:
        jobs.settings = settings()
        jobs.bind(dataset, "file", ReferenceSettings(), None)
        jobs.request_profile()
        deadline = monotonic() + 3
        while jobs.busy and monotonic() < deadline:
            jobs.poll()
            sleep(0.001)
        corpus = jobs.profile
        assert corpus is not None
        jobs.request_document()
        while jobs.busy and monotonic() < deadline:
            jobs.poll()
            sleep(0.001)
        assert jobs.active and jobs.active.document.origin.element_path == (0, 0)
        jobs.settings = replace(jobs.settings, element_index=3)
        jobs.bind(dataset, "file", ReferenceSettings(), None)
        assert jobs.active is None and jobs.profile is corpus
        jobs.request_document()
        while jobs.busy and monotonic() < deadline:
            jobs.poll()
            sleep(0.001)
        assert jobs.active and jobs.active.document.origin.element_path == (2, 1)
        restored = decode_record(TextSettings, encode(jobs.settings))
        assert restored.element_index == 3
        legacy = encode(jobs.settings)
        assert isinstance(legacy, dict)
        legacy.pop("element_index")
        assert decode_record(TextSettings, legacy).element_index == 0
    finally:
        jobs.close()


def test_list_training_records_element_paths_and_comparisons_select_parent_rows(
    tmp_path: Path,
) -> None:
    dataset = data(tmp_path)
    before = dataset.source.path.read_bytes()
    value = replace(
        settings(),
        training=TrainingSettings(
            output_path=str(tmp_path / "tokenizer.json"), vocabulary_size=32
        ),
    )
    trained = train_tokenizer(
        dataset, "file", value, (), ReferenceSettings(), None, Event(), TextProgress()
    )
    assert (trained.requested, trained.documents, trained.nulls, trained.empty) == (
        5,
        4,
        1,
        1,
    )
    assert trained.reference.provenance_path is not None
    provenance = json.loads(Path(trained.reference.provenance_path).read_text())
    assert provenance["source_row_ids"] == [0, 0, 0, 0, 1, 4]
    assert provenance["source_element_paths"] == [
        [0, 0],
        [0, 1],
        [2, 0],
        [2, 1],
        [0, 0],
        [0, 0],
    ]
    first = profile(dataset)
    second = replace(first, file_id="second")
    config = TextComparisonSettings(
        sources=(
            TextComparisonSource("file", "text"),
            TextComparisonSource("second", "text"),
        )
    )
    comparison = compare_profiles((first, second), ("first", "second"), config)
    chosen = select_length_bin(comparison, 0, 0, dataset)
    assert chosen.row_ids == (0,) and chosen.matches == 1
    assert dataset.source.path.read_bytes() == before


def test_empty_list_leaves_allow_explicit_meanings_without_inventing_values() -> None:
    dataset = Dataset.from_source(
        pl.DataFrame({"text": [[], None, [None]]}),
        SourceReference(Path("unused"), 0, 0),
    )
    assert dataset.table.schema["text"] == pl.List(pl.Null)
    text = Pipeline.start(dataset).apply(SetColumnRole("text", ColumnRole.LIST_TEXT))
    result = profile(text.current)
    assert (result.requested_records, result.documents, result.nulls) == (3, 0, 1)
    assert result.records["element_path"].to_list() == [[0]]
    assert result.token_lengths.mean is None
    numeric = Pipeline.start(dataset).apply(
        SetColumnRole("text", ColumnRole.LIST_NUMERIC)
    )
    group = prepare_profile_group(
        numeric.current, ProfileRequest(DistributionSettings(("text",)))
    )
    values = group.profiles.columns[0]
    assert values.statistics is not None and values.statistics.mean is None
    assert values.list_statistics is not None and values.list_statistics.elements == 1
    assert dataset.table["text"].to_list() == [[], None, [None]]
