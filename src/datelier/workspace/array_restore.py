"""Metadata-only mapped-view restoration before explicit scalar preparation."""

from dataclasses import dataclass, replace
from pathlib import Path

from datelier.inspection.arrays.types import ArrayCatalog
from datelier.inspection.exploration import PlotSettings
from datelier.io.types import ArrayOptions, ImportResult
from datelier.workspace.restore import restore_recipe
from datelier.workspace.session_types import SessionFile
from datelier.workspace.types import WorkspaceViews


@dataclass(frozen=True)
class DeferredArrayView:
    file: SessionFile
    catalog: ArrayCatalog
    imported: ImportResult
    changed: bool


def defer_array_view(
    file: SessionFile,
    *,
    relink: Path | None = None,
    accept_changed: bool = False,
    source_import: ImportResult | None = None,
) -> DeferredArrayView:
    recipe = file.recipe
    if (
        recipe is None
        or not isinstance(recipe.options, ArrayOptions)
        or recipe.options.mapping is None
    ):
        raise ValueError("Deferred array records require a saved mapping")
    metadata_options = replace(recipe.options, mapping=None, record_table=False)
    metadata_recipe = replace(
        recipe,
        options=metadata_options,
        history=(),
        cursor=0,
        analysis=(),
        plots=PlotSettings(),
        views=WorkspaceViews(),
    )
    prepared = (
        source_import
        if source_import is not None and source_import.options == metadata_options
        else None
    )
    restored = restore_recipe(
        metadata_recipe,
        relink=relink,
        accept_changed=accept_changed,
        imported_override=prepared,
    )
    imported = restored.inspection.imported
    catalog = imported.array_catalog
    if catalog is None:
        raise ValueError("Array metadata is unavailable")
    count = recipe.options.mapping.record_count(catalog)
    changed = recipe.source.sha256 != restored.workspace.source.sha256
    selection = () if changed else tuple(row for row in file.selection if row < count)
    updated = replace(
        file,
        recipe=replace(recipe, source=restored.workspace.source),
        selection=selection,
    )
    return DeferredArrayView(updated, catalog, imported, changed)
