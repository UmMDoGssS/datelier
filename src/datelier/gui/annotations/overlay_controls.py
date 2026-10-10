"""View-only source/class/score options beside the focused image."""

from dataclasses import replace

from imgui_bundle import imgui

from datelier.gui.components.help import show_help
from datelier.inspection.annotations.association_types import PreparedAnnotations
from datelier.inspection.annotations.overlay import OverlayClass, OverlaySettings


def overlay_controls(
    settings: OverlaySettings, prepared: PreparedAnnotations | None
) -> OverlaySettings:
    _, enabled = imgui.checkbox("Box overlays", settings.enabled)
    settings = replace(settings, enabled=enabled)
    if prepared is None:
        if settings.enabled:
            imgui.same_line()
            imgui.text("Load sources under Detection annotations.")
        return settings
    imgui.same_line()
    if imgui.tree_node("Overlay sources and filters"):
        if imgui.button("All annotation sources"):
            settings = replace(settings, sources=None)
        for index, source in enumerate(prepared.sources):
            imgui.push_id(source.recipe.id)
            selected = settings.sources is None or source.recipe.id in settings.sources
            changed, selected = imgui.checkbox(
                source.recipe.name or f"Source {index + 1}", selected
            )
            if changed:
                sources = (
                    list(settings.sources)
                    if settings.sources is not None
                    else [item.recipe.id for item in prepared.sources]
                )
                if selected and source.recipe.id not in sources:
                    sources.append(source.recipe.id)
                elif not selected and source.recipe.id in sources:
                    sources.remove(source.recipe.id)
                settings = replace(settings, sources=tuple(sources))
            imgui.pop_id()
        _, labels = imgui.checkbox("Class labels", settings.labels)
        _, overlapping = imgui.checkbox(
            "Show overlapping box labels", settings.overlapping_labels
        )
        imgui.same_line()
        _, scores = imgui.checkbox("Confidence labels", settings.scores)
        _, unscored = imgui.checkbox(
            "Include boxes without scores", settings.include_unscored
        )
        _, threshold = imgui.checkbox(
            "Minimum box score", settings.minimum_score is not None
        )
        value = settings.minimum_score if settings.minimum_score is not None else 0.0
        if threshold:
            imgui.set_next_item_width(140)
            changed, value = imgui.input_double("Score threshold", value)
            if changed:
                try:
                    replace(settings, minimum_score=value).validate()
                except ValueError:
                    value = settings.minimum_score or 0.0
        _, limit = imgui.input_int("Visible box limit", settings.limit)
        settings = replace(
            settings,
            labels=labels,
            overlapping_labels=overlapping,
            scores=scores,
            include_unscored=unscored,
            minimum_score=value if threshold else None,
            limit=max(1, limit),
        )
        if imgui.tree_node("Overlay classes"):
            if imgui.button("All annotation classes"):
                settings = replace(settings, classes=None)
            if imgui.begin_child("Overlay class checklist", (0, 140)):
                for index, source in enumerate(prepared.sources):
                    classes = prepared.overlay_classes.get(source.recipe.id, ())
                    imgui.push_id(source.recipe.id)
                    imgui.text_unformatted(source.recipe.name or f"Source {index + 1}")
                    clipper = imgui.ListClipper()
                    clipper.begin(len(classes))
                    while clipper.step():
                        for ordinal in range(
                            clipper.display_start, clipper.display_end
                        ):
                            item = classes[ordinal]
                            key = OverlayClass(source.recipe.id, item.id)
                            selected = (
                                settings.classes is None or key in settings.classes
                            )
                            changed, selected = imgui.checkbox(
                                f"{item.name} / {item.id}", selected
                            )
                            if changed:
                                current = (
                                    list(settings.classes)
                                    if settings.classes is not None
                                    else [
                                        OverlayClass(s.recipe.id, c.id)
                                        for s in prepared.sources
                                        for c in prepared.overlay_classes.get(
                                            s.recipe.id, ()
                                        )
                                    ]
                                )
                                if selected and key not in current:
                                    current.append(key)
                                elif not selected and key in current:
                                    current.remove(key)
                                settings = replace(settings, classes=tuple(current))
                    imgui.pop_id()
            imgui.end_child()
            imgui.tree_pop()
        show_help("Click a box to select it; Ctrl-click cycles overlapping boxes.")
        imgui.tree_pop()
    return settings
