"""Explicit media manifest refresh and metadata-first source settings."""

from datelier.application.imports.media import MediaDraft
from datelier.gui.components.actions import CommandButton
from datelier.gui.components.fields import BooleanField
from datelier.gui.sources.imports.base import OptionForm


class MediaForm(OptionForm):
    description = (
        "File records open lazily. Line records read text on explicit import. "
        "Saved manifests retain the same records unless refreshed."
    )

    def __init__(self, model: MediaDraft) -> None:
        super().__init__(
            "media",
            (
                BooleanField(
                    "lines",
                    "Text: one record per line",
                    lambda: model.lines,
                    lambda v: setattr(model, "lines", v),
                ),
                BooleanField(
                    "recursive",
                    "Include media subfolders",
                    lambda: model.recursive,
                    lambda v: setattr(model, "recursive", v),
                ),
                CommandButton("refresh", "Refresh manifest on import", model.refresh),
            ),
        )
