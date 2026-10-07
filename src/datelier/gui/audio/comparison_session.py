"""Editor audio contributors and source-scoped record navigation, without decoding."""

from dataclasses import replace
from typing import TYPE_CHECKING

from datelier.inspection.audio.comparisons.settings import AudioComparisonSettings
from datelier.inspection.audio.comparisons.types import (
    AudioComparisonInput,
    PreparedAudioComparison,
)
from datelier.inspection.comparisons.types import ComparisonSelection, Origin
from datelier.inspection.records.types import RecordMode
from datelier.io.types import ArrayOptions

if TYPE_CHECKING:
    from datelier.gui.editor_session import EditorSession


def comparison_inputs(
    editor: EditorSession, recipe: AudioComparisonSettings
) -> tuple[AudioComparisonInput, ...]:
    files = {file.identity: file for file in editor.file_sessions}
    inputs = []
    for number, source in enumerate(recipe.sources):
        file = files.get(source.file_id)
        if file is None or file.loader.active is None:
            continue
        active = file.loader.active
        options = active.imported.options
        mapping = options.mapping if isinstance(options, ArrayOptions) else None
        inputs.append(
            AudioComparisonInput(
                source,
                active.dataset,
                f"{number + 1}: {active.dataset.source.path.name} {file.view_name} / "
                f"{source.profile.column}",
                file.view_name,
                file.references.settings,
                file.references.index,
                tuple(sorted(file.selection.row_ids)),
                file.arrays.store,
                active.imported.array_catalog,
                mapping,
            )
        )
    return tuple(inputs)


def sync_comparisons(editor: EditorSession) -> None:
    known = {file.identity for file in editor.file_sessions}
    editor.audio_comparisons = tuple(
        replace(recipe, sources=tuple(s for s in recipe.sources if s.file_id in known))
        for recipe in editor.audio_comparisons
    )
    editor.audio_comparison_index = min(
        editor.audio_comparison_index, max(0, len(editor.audio_comparisons) - 1)
    )
    recipe = (
        editor.audio_comparisons[editor.audio_comparison_index]
        if editor.audio_comparisons
        else None
    )
    editor.audio_comparison_jobs.bind(
        recipe, comparison_inputs(editor, recipe) if recipe else ()
    )


def open_record(
    editor: EditorSession, result: PreparedAudioComparison, source: int, row: int
) -> None:
    if editor.audio_comparison_jobs.active is not result:
        raise ValueError("Audio comparison changed; prepare a current result")
    if (
        not 0 <= source < len(result.profiles)
        or not 0 <= row < result.profiles[source].records.height
    ):
        raise ValueError("Choose an available audio source record")
    profile = result.profiles[source]
    file = next(
        (f for f in editor.file_sessions if f.identity == profile.file_id), None
    )
    if file is None or file.loader.revision != profile.revision:
        raise ValueError("Audio source changed or closed")
    editor.apply_comparison_selection(
        ComparisonSelection(
            Origin(
                profile.file_id,
                profile.revision,
                profile.settings.column or "",
                profile.view_name,
            ),
            (int(profile.records["row_id"][row]),),
            1,
            int(profile.records["position"][row]),
        )
    )
    file.inspect.settings = replace(
        file.inspect.settings,
        mode=RecordMode.SELECTION,
        primary=profile.settings.column,
        focus=0,
        gallery=False,
    )
    file.audio.settings = replace(
        file.audio.settings,
        array_sample_rate=profile.settings.array_sample_rate,
        thresholds=profile.settings.thresholds,
    )
    file.exploration.tab = "Inspect"
    file.focus_inspect = editor.active.focus_inspect = True
