"""Explicit source/scope mapping and copying one visible token recipe."""

from dataclasses import replace

from imgui_bundle import imgui

from datelier.gui.editor_session import EditorSession
from datelier.gui.text.training import scope_controls
from datelier.inspection.text.comparisons.settings import (
    TextComparisonSettings,
    TextComparisonSource,
    TextScale,
)
from datelier.inspection.text.list_records import is_text_field, is_text_list
from datelier.inspection.text.types import TextSource


def controls(
    editor: EditorSession, settings: TextComparisonSettings
) -> TextComparisonSettings:
    tokens = settings.tokens
    active = editor.active.record_views.active(editor.active)
    if imgui.button("Use active view tokenizer"):
        tokens = active.text.jobs.settings.tokens
    imgui.text_wrapped(
        f"Shared tokenizer: {tokens.mode} · {tokens.normalization} · "
        f"lowercase {tokens.lowercase} · whitespace {tokens.character_whitespace} · "
        f"add/count specials {tokens.add_special_tokens}/{tokens.count_special_tokens}"
    )
    if tokens.artifact is not None:
        imgui.text_wrapped(f"Local artifact: {tokens.artifact.path}")
        imgui.text_wrapped(f"SHA-256: {tokens.artifact.sha256}")
    imgui.text_wrapped(
        "Configure tokenization in Explore → Profiles, then copy it here. "
        "This shared configuration "
        "applies to every mapped field; no training or downloads start here."
    )
    _, bins = imgui.input_int("Shared length bins", settings.bins)
    scales = list(TextScale)
    _, scale = imgui.combo(
        "Text comparison scale", scales.index(settings.scale), [s.value for s in scales]
    )
    sources = list(settings.sources)
    files = {f.identity: f for f in editor.file_sessions}
    for source in sources:
        if source.file_id not in files:
            imgui.text_wrapped(
                f"Unavailable source {source.file_id}; recover or remove it."
            )
    for file in editor.file_sessions:
        imgui.push_id(file.identity)
        current = next((s for s in sources if s.file_id == file.identity), None)
        dataset = file.loader.active.dataset if file.loader.active else None
        label = (dataset.source.path.name if dataset else "Unavailable") + (
            f" / {file.view_name}" if file.view_name else ""
        )
        changed, use = imgui.checkbox(label, current is not None)
        columns = (
            [
                name
                for name, dtype in dataset.table.schema.items()
                if is_text_field(dtype)
            ]
            if dataset
            else []
        )
        if changed:
            sources = [s for s in sources if s.file_id != file.identity]
            if use and columns:
                text = file.text.jobs.settings
                current = TextComparisonSource(
                    file.identity,
                    text.column
                    if text.column is not None and text.column in columns
                    else columns[0],
                    text.source,
                    text.encoding,
                    text.scope,
                )
                sources.append(current)
            else:
                current = None
        if current is not None and imgui.tree_node("Field and corpus scope"):
            names = ["Unavailable field", *columns]
            chosen = names.index(current.column) if current.column in names else 0
            _, chosen = imgui.combo("Mapped text field", chosen, names)
            chosen_column = names[chosen] if chosen else current.column
            text_list = (
                dataset is not None
                and chosen_column in columns
                and is_text_list(dataset.table.schema[chosen_column])
            )
            modes = (
                [TextSource.AUTO, TextSource.INLINE] if text_list else list(TextSource)
            )
            _, mode = imgui.combo(
                "Mapped text source",
                modes.index(current.source) if current.source in modes else 0,
                [m.value for m in modes],
            )
            encodings = ["utf8", "utf-8-sig", "utf16", "latin1"]
            _, encoding = imgui.combo(
                "Mapped encoding", encodings.index(current.encoding), encodings
            )
            updated = replace(
                current,
                column=chosen_column,
                source=modes[mode],
                encoding=encodings[encoding],
                scope=scope_controls(current.scope),
            )
            sources = [updated if s.file_id == file.identity else s for s in sources]
            imgui.tree_pop()
        imgui.pop_id()
    return replace(
        settings,
        sources=tuple(sources),
        tokens=tokens,
        bins=max(1, min(bins, 200)),
        scale=scales[scale],
    )
