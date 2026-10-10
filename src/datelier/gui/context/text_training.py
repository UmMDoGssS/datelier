"""Related explicit tokenizer training forms over one scoped text controller."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import replace

from datelier.application.text import TextController
from datelier.gui.components.actions import CommandButton
from datelier.gui.components.base import Container, FrameContext
from datelier.gui.components.fields import (
    ChoiceField,
    FloatField,
    IntegerField,
    TextField,
)
from datelier.inspection.text.types import TokenMode


class TrainingForm(Container, ABC):
    def __init__(
        self,
        key: str,
        model: TextController,
        extra: tuple[Container | IntegerField | FloatField, ...] = (),
    ) -> None:
        self.model = model

        def setting(
            name: str,
            label: str,
            get: Callable[[], int],
            set_value: Callable[[int], None],
            minimum: int,
            maximum: int,
        ) -> IntegerField:
            return IntegerField(name, label, get, set_value, minimum, maximum)

        super().__init__(
            key,
            (
                setting(
                    "vocabulary",
                    "Vocabulary size",
                    lambda: model.jobs.settings.training.vocabulary_size,
                    lambda value: self.set_vocabulary(value),
                    2,
                    1000000,
                ),
                setting(
                    "frequency",
                    "Minimum frequency",
                    lambda: model.jobs.settings.training.min_frequency,
                    lambda value: self.set_frequency(value),
                    1,
                    1000000,
                ),
                setting(
                    "piece",
                    "Maximum piece length",
                    lambda: model.jobs.settings.training.max_piece_length,
                    lambda value: self.set_piece(value),
                    1,
                    1000000,
                ),
                *extra,
                TextField(
                    "special",
                    "Special tokens (one per line; first is [UNK])",
                    lambda: "\n".join(model.jobs.settings.training.special_tokens),
                    lambda value: setattr(
                        model.jobs,
                        "settings",
                        replace(
                            model.jobs.settings,
                            training=replace(
                                model.jobs.settings.training,
                                special_tokens=tuple(value.splitlines()),
                            ),
                        ),
                    ),
                    multiline=True,
                ),
                TextField(
                    "output",
                    "New tokenizer JSON path",
                    lambda: model.jobs.settings.training.output_path,
                    lambda value: setattr(
                        model.jobs,
                        "settings",
                        replace(
                            model.jobs.settings,
                            training=replace(
                                model.jobs.settings.training, output_path=value
                            ),
                        ),
                    ),
                ),
            ),
        )

    def set_vocabulary(self, value: int) -> None:
        self.model.jobs.settings = replace(
            self.model.jobs.settings,
            training=replace(self.model.jobs.settings.training, vocabulary_size=value),
        )

    def set_frequency(self, value: int) -> None:
        self.model.jobs.settings = replace(
            self.model.jobs.settings,
            training=replace(self.model.jobs.settings.training, min_frequency=value),
        )

    def set_piece(self, value: int) -> None:
        self.model.jobs.settings = replace(
            self.model.jobs.settings,
            training=replace(self.model.jobs.settings.training, max_piece_length=value),
        )

    @property
    @abstractmethod
    def mode(self) -> TokenMode: ...


class BpeTrainingForm(TrainingForm):
    def __init__(self, model: TextController) -> None:
        super().__init__("bpe", model)

    @property
    def mode(self) -> TokenMode:
        return TokenMode.BPE


class UnigramTrainingForm(TrainingForm):
    def __init__(self, model: TextController) -> None:
        super().__init__(
            "unigram",
            model,
            (
                IntegerField(
                    "iterations",
                    "Iterations",
                    lambda: model.jobs.settings.training.iterations,
                    lambda value: setattr(
                        model.jobs,
                        "settings",
                        replace(
                            model.jobs.settings,
                            training=replace(
                                model.jobs.settings.training, iterations=value
                            ),
                        ),
                    ),
                    1,
                    100,
                ),
                FloatField(
                    "shrinking",
                    "Shrinking factor",
                    lambda: model.jobs.settings.training.shrinking_factor,
                    lambda value: setattr(
                        model.jobs,
                        "settings",
                        replace(
                            model.jobs.settings,
                            training=replace(
                                model.jobs.settings.training, shrinking_factor=value
                            ),
                        ),
                    ),
                    0.01,
                    0.99,
                ),
            ),
        )

    @property
    def mode(self) -> TokenMode:
        return TokenMode.UNIGRAM


class TrainingSettings(Container):
    def __init__(self, model: TextController, column: Callable[[], str]) -> None:
        self.model = model
        self.forms = {
            form.mode: form
            for form in (BpeTrainingForm(model), UnigramTrainingForm(model))
        }
        self.mode_field = ChoiceField(
            "mode",
            "Training method",
            (TokenMode.BPE, TokenMode.UNIGRAM),
            lambda: model.jobs.settings.training.mode,
            lambda value: setattr(
                model.jobs,
                "settings",
                replace(
                    model.jobs.settings,
                    training=replace(model.jobs.settings.training, mode=value),
                ),
            ),
        )
        self.command = CommandButton(
            "train",
            "Train on chosen corpus",
            lambda: model.request_training(column()),
            lambda: not model.corpus.busy,
        )
        super().__init__("training", ())

    def render(self, frame: FrameContext) -> None:
        self.children = (
            self.mode_field,
            self.command,
            self.forms[self.model.jobs.settings.training.mode],
        )
        super().render(frame)
