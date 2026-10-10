"""Explicit annotation commands and contextual overlay filters."""

from collections.abc import Callable
from dataclasses import replace

from datelier.application.annotations.controller import AnnotationController
from datelier.application.columns import MultiSelection, SingleSelection
from datelier.gui.annotations.sources import SourceForm
from datelier.gui.components.actions import CommandButton, JobFeedback, JobSnapshot
from datelier.gui.components.base import Container
from datelier.gui.components.bindings import StateFields
from datelier.gui.components.columns import ColumnPicker
from datelier.gui.components.groups import Collapsible


class AnnotationSettings(Container):
    def __init__(self, model: AnnotationController, column: Callable[[], str]) -> None:
        view = StateFields(model.read_view, model.write_view)
        overlay = StateFields(
            lambda: model.read_view().overlay,
            lambda value: model.write_view(replace(model.read_view(), overlay=value)),
        )
        super().__init__(
            "annotation-settings",
            (
                ColumnPicker(
                    "image-column",
                    "Annotation image field",
                    lambda: model.columns,
                    lambda: (
                        (column,) if (column := model.read_settings().column) else ()
                    ),
                    lambda names: model.write_settings(
                        replace(model.read_settings(), column=next(iter(names), None))
                    ),
                    SingleSelection(),
                ),
                CommandButton(
                    "associate",
                    "Load / associate annotations",
                    lambda: model.request(column()),
                    lambda: not model.jobs.busy,
                ),
                JobFeedback(
                    "job",
                    lambda: JobSnapshot(
                        model.jobs.message,
                        model.jobs.busy,
                        str(model.jobs.progress.value),
                    ),
                    model.abandon,
                ),
                Collapsible(
                    "sources", "Annotation sources and mappings", (SourceForm(model),)
                ),
                Collapsible(
                    "overlays",
                    "Box overlays",
                    (
                        overlay.boolean(
                            "enabled",
                            "Show boxes",
                            lambda s: s.enabled,
                            lambda s, v: replace(s, enabled=v),
                        ),
                        ColumnPicker(
                            "sources",
                            "Visible annotation sources",
                            lambda: model.source_choices,
                            lambda: (
                                sources
                                if (sources := overlay.read().sources) is not None
                                else tuple(s.name for s in model.source_choices)
                            ),
                            lambda names: overlay.write(
                                replace(overlay.read(), sources=names)
                            ),
                            MultiSelection(),
                        ),
                        ColumnPicker(
                            "classes",
                            "Visible classes",
                            lambda: model.class_choices,
                            model.class_selection,
                            model.choose_classes,
                            MultiSelection(),
                        ),
                        CommandButton(
                            "all",
                            "Include all sources and classes",
                            lambda: overlay.write(
                                replace(overlay.read(), sources=None, classes=None)
                            ),
                        ),
                        overlay.floating(
                            "score",
                            "Minimum score (0 = no threshold)",
                            lambda s: s.minimum_score or 0,
                            lambda s, v: replace(s, minimum_score=v or None),
                            -1e300,
                            1e300,
                        ),
                        overlay.boolean(
                            "unscored",
                            "Include unscored boxes",
                            lambda s: s.include_unscored,
                            lambda s, v: replace(s, include_unscored=v),
                        ),
                        overlay.boolean(
                            "labels",
                            "Class labels",
                            lambda s: s.labels,
                            lambda s, v: replace(s, labels=v),
                        ),
                        overlay.boolean(
                            "scores",
                            "Confidence labels",
                            lambda s: s.scores,
                            lambda s, v: replace(s, scores=v),
                        ),
                        overlay.boolean(
                            "overlap",
                            "Allow overlapping labels",
                            lambda s: s.overlapping_labels,
                            lambda s, v: replace(s, overlapping_labels=v),
                        ),
                        overlay.integer(
                            "limit",
                            "Visible box limit",
                            lambda s: s.limit,
                            lambda s, v: replace(s, limit=v),
                            1,
                        ),
                    ),
                ),
                Collapsible(
                    "profiles",
                    "Annotation profiles",
                    (
                        CommandButton(
                            "prepare",
                            "Prepare annotation statistics",
                            model.request_profiles,
                            lambda: (
                                model.jobs.active is not None
                                and not model.profiles.busy
                            ),
                        ),
                        JobFeedback(
                            "profile-job",
                            lambda: JobSnapshot(
                                model.profiles.message,
                                model.profiles.busy,
                                str(model.profiles.progress.value),
                            ),
                            model.abandon_profiles,
                        ),
                        view.integer(
                            "bins",
                            "Size histogram bins",
                            lambda s: s.bins,
                            lambda s, v: replace(s, bins=v),
                            1,
                            256,
                        ),
                        view.choice(
                            "distribution",
                            "Box size",
                            ("Width", "Height", "Area", "Aspect ratio"),
                            lambda s: s.distribution,
                            lambda s, v: replace(s, distribution=v),
                        ),
                    ),
                ),
            ),
        )
