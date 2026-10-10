"""Shared tokenization controls plus explicit corpus/import/training commands."""

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from imgui_bundle import imgui

from datelier.application.text import TextController
from datelier.gui.components.actions import CommandButton, JobFeedback, JobSnapshot
from datelier.gui.components.base import Container, FrameContext
from datelier.gui.components.fields import ChoiceField, TextField
from datelier.gui.components.groups import Collapsible
from datelier.gui.context.media import TokenSettings
from datelier.gui.context.text_scope import TextScopeFields
from datelier.gui.context.text_training import TrainingSettings
from datelier.inspection.text.types import TextSource


class TextProfileSettings(Container):
    def __init__(self, model: TextController, column: Callable[[], str]) -> None:
        self.model = model
        self.path = ""
        super().__init__(
            "text-profile-settings",
            (
                CommandButton(
                    "profile",
                    "Calculate exact corpus profile",
                    lambda: model.request_profile(column()),
                    lambda: not model.corpus.busy,
                ),
                JobFeedback("corpus-job", self.feedback, model.corpus.abandon),
                TextScopeFields(
                    lambda: model.jobs.settings.scope,
                    lambda value: setattr(
                        model.jobs,
                        "settings",
                        replace(model.jobs.settings, scope=value),
                    ),
                ),
                Collapsible(
                    "tokenizer",
                    "Tokenizer",
                    (
                        ChoiceField(
                            "source",
                            "Text source",
                            tuple(TextSource),
                            lambda: model.jobs.settings.source,
                            lambda value: setattr(
                                model.jobs,
                                "settings",
                                replace(model.jobs.settings, source=value),
                            ),
                        ),
                        ChoiceField(
                            "encoding",
                            "Encoding",
                            ("utf8", "utf-8-sig", "utf16", "latin1"),
                            lambda: model.jobs.settings.encoding,
                            lambda value: setattr(
                                model.jobs,
                                "settings",
                                replace(model.jobs.settings, encoding=value),
                            ),
                        ),
                        TokenSettings(model, page=False),
                        TextField(
                            "path",
                            "Local tokenizer JSON",
                            lambda: self.path,
                            lambda value: setattr(self, "path", value),
                        ),
                        CommandButton(
                            "import",
                            "Load local tokenizer",
                            lambda: model.corpus.request_import(Path(self.path)),
                        ),
                    ),
                ),
                Collapsible(
                    "train",
                    "Train tokenizer explicitly",
                    (TrainingSettings(model, column),),
                ),
            ),
        )

    def feedback(self) -> JobSnapshot:
        phase, done, total = self.model.corpus.progress.value
        return JobSnapshot(
            self.model.corpus.message,
            self.model.corpus.busy,
            f"{phase}: {done:,} / {total:,}" if phase else "",
        )

    def render(self, frame: FrameContext) -> None:
        artifact = self.model.jobs.settings.tokens.artifact
        if artifact:
            imgui.text_wrapped(f"Local {artifact.mode}: {artifact.path}")
            imgui.text_wrapped(f"Tokenizer SHA-256: {artifact.sha256}")
        super().render(frame)
