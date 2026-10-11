"""Audio collection tables render worker results without decoded signals."""

from dataclasses import replace

from imgui_bundle import imgui

from datelier.application.exploration import ProfileFamily
from datelier.application.media.audio import AudioController
from datelier.gui.components.base import FrameContext
from datelier.gui.components.dataframe import DataFrameTable
from datelier.gui.profiles.base import ProfileContent
from datelier.gui.shell.navigation import CanvasTabs, NamedTab


class AudioProfileContent(ProfileContent):
    def __init__(self, model: AudioController) -> None:
        self.model = model
        super().__init__(
            "audio-profile",
            (
                CanvasTabs(
                    (
                        NamedTab(
                            "Records",
                            DataFrameTable(
                                "record-outcomes",
                                lambda: (
                                    model.collection.active.records
                                    if model.collection.active
                                    else None
                                ),
                                300,
                            ),
                        ),
                        NamedTab(
                            "Channels",
                            DataFrameTable(
                                "channel-statistics",
                                lambda: (
                                    model.collection.active.channel_records
                                    if model.collection.active
                                    else None
                                ),
                                300,
                            ),
                        ),
                    ),
                    lambda: model.settings.profile_tab,
                    lambda value: setattr(
                        model, "settings", replace(model.settings, profile_tab=value)
                    ),
                ),
            ),
        )

    @property
    def family(self) -> ProfileFamily:
        return ProfileFamily.AUDIO

    def render(self, frame: FrameContext) -> None:
        imgui.text_wrapped(self.model.collection.message)
        profile = self.model.collection.active
        if profile:
            imgui.text_wrapped(
                f"{profile.settings.column} · {profile.settings.mode} · "
                f"{profile.settings.scope.mode} · {profile.ready:,} ready / "
                f"{profile.available_records:,} available"
            )
            imgui.text_wrapped(
                "Signal values retain their original units and rate. "
                "Header profiles do not decode samples."
            )
            super().render(frame)
