"""Manifest-preserving media import drafts; rescanning is an explicit command."""

from dataclasses import replace

from datelier.application.imports.base import OptionsDraft, option
from datelier.io.types import ImportOptions, MediaOptions


class MediaDraft(OptionsDraft):
    def __init__(self) -> None:
        self.bind(MediaOptions())

    def bind(self, value: ImportOptions) -> None:
        self.base = option(value, MediaOptions)
        self.lines, self.recursive = self.base.text_lines, self.base.recursive

    def refresh(self) -> None:
        self.base = replace(self.base, manifest=None, line_counts=())

    def build(self) -> MediaOptions:
        unchanged = (
            self.lines == self.base.text_lines and self.recursive == self.base.recursive
        )
        return replace(
            self.base,
            text_lines=self.lines,
            recursive=self.recursive,
            manifest=self.base.manifest if unchanged else None,
            line_counts=self.base.line_counts if unchanged else (),
        )
