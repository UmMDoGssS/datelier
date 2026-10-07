"""Explicit image source/field and per-source scope choices."""

from dataclasses import replace

import polars as pl
from imgui_bundle import imgui

from datelier.core.column_roles import ColumnRole
from datelier.gui.editor_session import EditorSession
from datelier.gui.images.profile_controls import profile_controls
from datelier.inspection.arrays.mapping import ArrayLayout
from datelier.inspection.images.comparisons.settings import (
    ImageComparisonSettings,
    ImageComparisonSource,
)
from datelier.io.types import ArrayOptions


def controls(
    editor: EditorSession, recipe: ImageComparisonSettings
) -> ImageComparisonSettings:
    _, bins = imgui.input_int("Common image bins", recipe.bins)
    recipe = replace(recipe, bins=max(1, min(256, bins)))
    sources = {source.file_id: source for source in recipe.sources}
    for file in editor.file_sessions:
        imgui.push_id(file.identity)
        active = file.loader.active
        if active is None:
            imgui.text_wrapped(
                f"Unavailable: {file.controls.path}. "
                "Recover this source before comparing."
            )
            imgui.pop_id()
            continue
        options = active.imported.options
        mapping = options.mapping if isinstance(options, ArrayOptions) else None
        fields = [
            name
            for name, dtype in active.dataset.table.schema.items()
            if dtype == pl.String
        ]
        if mapping is not None and mapping.layout == ArrayLayout.IMAGE:
            fields = [mapping.member]
        if not fields:
            imgui.pop_id()
            continue
        label = f"Include {active.dataset.source.path.name} {file.view_name}"
        changed, included = imgui.checkbox(label, file.identity in sources)
        if changed:
            if included:
                selected = next(
                    (
                        name
                        for name in fields
                        if name in active.dataset.table.columns
                        and active.dataset.role(name).role == ColumnRole.IMAGE
                    ),
                    fields[0],
                )
                profile = replace(
                    file.images.settings.profile, column=selected, bins=recipe.bins
                )
                sources[file.identity] = ImageComparisonSource(file.identity, profile)
            else:
                sources.pop(file.identity, None)
        source = sources.get(file.identity)
        if source is not None:
            profile = source.profile
            available = profile.column in fields
            names = fields if available else [f"Unavailable: {profile.column}", *fields]
            current = (
                fields.index(profile.column)
                if profile.column is not None and profile.column in fields
                else 0
            )
            changed, current = imgui.combo("Compared image field", current, names)
            if changed and (available or current > 0):
                profile = replace(profile, column=names[current])
            profile = replace(profile, bins=recipe.bins)
            sources[file.identity] = replace(
                source, profile=profile_controls(profile, show_bins=False)
            )
        imgui.pop_id()
    imgui.text_wrapped(
        "Scopes and pixel samples are independent per source. "
        "Histograms use common physical bins; colors keep mode and dtype "
        "families separate."
    )
    return replace(recipe, sources=tuple(sources.values()))
