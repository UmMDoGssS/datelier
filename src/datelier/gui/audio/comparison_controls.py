"""Explicit source field, record scope, decode mode and original-unit thresholds."""

from dataclasses import replace
from math import isfinite

import polars as pl
from imgui_bundle import imgui

from datelier.core.column_roles import ColumnRole
from datelier.gui.editor_session import EditorSession
from datelier.inspection.arrays.mapping import ArrayLayout
from datelier.inspection.audio.collections.settings import (
    AudioCollectionSettings,
    AudioProfileMode,
    AudioScopeMode,
)
from datelier.inspection.audio.comparisons.settings import (
    AudioComparisonSettings,
    AudioComparisonSource,
)
from datelier.io.types import ArrayOptions


def profile_controls(
    settings: AudioCollectionSettings, array: bool
) -> AudioCollectionSettings:
    scope = settings.scope
    modes = list(AudioScopeMode)
    _, choice = imgui.combo(
        "Compared audio records", modes.index(scope.mode), [m.value for m in modes]
    )
    scope = replace(scope, mode=modes[choice])
    if scope.mode == AudioScopeMode.RANGE:
        _, first = imgui.input_int("First compared audio row", scope.start)
        scope = replace(scope, start=max(1, first))
    if scope.mode in (AudioScopeMode.RANGE, AudioScopeMode.RANDOM):
        _, count = imgui.input_int("Compared audio record count", scope.count)
        scope = replace(scope, count=max(1, count))
    if scope.mode == AudioScopeMode.RANDOM:
        _, seed = imgui.input_int("Compared audio seed", scope.seed)
        scope = replace(scope, seed=max(0, min(seed, 2**32 - 1)))
    levels = list(AudioProfileMode)
    _, choice = imgui.combo(
        "Compared audio statistics",
        levels.index(settings.mode),
        [m.value for m in levels],
    )
    settings = replace(settings, scope=scope, mode=levels[choice])
    if array:
        _, rate = imgui.input_int(
            "Compared sample rate (Hz; 0 = unknown)", settings.array_sample_rate or 0
        )
        settings = replace(
            settings, array_sample_rate=max(1, min(768000, rate)) if rate > 0 else None
        )
    if settings.mode == AudioProfileMode.SIGNAL:
        thresholds = settings.thresholds
        changed, rails = imgui.checkbox(
            "Compare original clipping rails", thresholds.clipping is None
        )
        if changed:
            thresholds = replace(thresholds, clipping=None if rails else 1.0)
        if thresholds.clipping is not None:
            _, value = imgui.input_double(
                "Compared clipping amplitude", thresholds.clipping
            )
            if isfinite(value) and value > 0:
                thresholds = replace(thresholds, clipping=value)
        _, silence = imgui.input_double(
            "Compared silence amplitude", thresholds.silence, format="%.6g"
        )
        if isfinite(silence) and silence >= 0:
            thresholds = replace(thresholds, silence=silence)
        settings = replace(settings, thresholds=thresholds)
    return settings


def controls(
    editor: EditorSession, recipe: AudioComparisonSettings
) -> AudioComparisonSettings:
    _, bins = imgui.input_int("Common audio bins", recipe.bins)
    recipe = replace(recipe, bins=max(1, min(256, bins)))
    sources = {s.file_id: s for s in recipe.sources}
    for file in editor.file_sessions:
        imgui.push_id(file.identity)
        active = file.loader.active
        if active is None:
            imgui.text_wrapped(
                f"Unavailable: {file.controls.path}. Recover before comparing."
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
        array = mapping is not None and mapping.layout == ArrayLayout.AUDIO
        if array:
            assert mapping is not None
            fields = [mapping.member]
        if not fields:
            imgui.pop_id()
            continue
        changed, included = imgui.checkbox(
            f"Include audio {active.dataset.source.path.name} {file.view_name}",
            file.identity in sources,
        )
        if changed:
            if included:
                selected = next(
                    (
                        name
                        for name in fields
                        if name in active.dataset.table.columns
                        and active.dataset.role(name).role == ColumnRole.AUDIO
                    ),
                    fields[0],
                )
                sources[file.identity] = AudioComparisonSource(
                    file.identity,
                    AudioCollectionSettings(
                        selected,
                        array_sample_rate=file.audio.settings.array_sample_rate,
                        thresholds=file.audio.settings.thresholds,
                    ),
                )
            else:
                sources.pop(file.identity, None)
        source = sources.get(file.identity)
        if source is not None:
            profile = source.profile
            available = profile.column in fields
            names = fields if available else [f"Unavailable: {profile.column}", *fields]
            current = fields.index(profile.column) if profile.column in fields else 0
            changed, current = imgui.combo("Compared audio field", current, names)
            if changed and (available or current > 0):
                profile = replace(profile, column=names[current])
            sources[file.identity] = replace(
                source, profile=profile_controls(profile, array)
            )
        imgui.pop_id()
    imgui.text_wrapped(
        "Headers do not decode samples. Exact signal statistics scan whole scoped "
        "records only after Prepare. Original rates and amplitude units are "
        "preserved; thresholds are independent per source."
    )
    return replace(recipe, sources=tuple(sources.values()))
