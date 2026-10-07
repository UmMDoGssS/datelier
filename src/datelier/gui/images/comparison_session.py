"""Editor-owned image inputs and explicit job binding, without frame computation."""

from dataclasses import replace
from typing import TYPE_CHECKING

from datelier.inspection.images.comparisons.settings import ImageComparisonSettings
from datelier.inspection.images.comparisons.types import ImageComparisonInput
from datelier.io.types import ArrayOptions

if TYPE_CHECKING:
    from datelier.gui.editor_session import EditorSession


def comparison_inputs(
    editor: EditorSession, recipe: ImageComparisonSettings
) -> tuple[ImageComparisonInput, ...]:
    files = {file.identity: file for file in editor.file_sessions}
    inputs = []
    for number, source in enumerate(recipe.sources):
        file = files.get(source.file_id)
        if file is None or file.loader.active is None:
            continue
        active = file.loader.active
        options = active.imported.options
        mapping = options.mapping if isinstance(options, ArrayOptions) else None
        label = (
            f"{number + 1}: {active.dataset.source.path.name} {file.view_name} / "
            f"{source.profile.column}"
        )
        inputs.append(
            ImageComparisonInput(
                source,
                active.dataset,
                label,
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
    editor.image_comparisons = tuple(
        replace(
            recipe,
            sources=tuple(
                source for source in recipe.sources if source.file_id in known
            ),
        )
        for recipe in editor.image_comparisons
    )
    editor.image_comparison_index = min(
        editor.image_comparison_index, max(0, len(editor.image_comparisons) - 1)
    )
    recipe = (
        editor.image_comparisons[editor.image_comparison_index]
        if editor.image_comparisons
        else None
    )
    editor.image_comparison_jobs.bind(
        recipe, comparison_inputs(editor, recipe) if recipe else ()
    )
