"""Metadata-first object, array and restricted checkpoint import drafts."""

from dataclasses import replace

from datelier.application.imports.base import OptionsDraft, option
from datelier.io.types import (
    ArrayOptions,
    CheckpointOptions,
    ImportOptions,
    ObjectOptions,
)


class ObjectDraft(OptionsDraft):
    def __init__(self) -> None:
        self.bind(ObjectOptions())

    def bind(self, value: ImportOptions) -> None:
        self.base = option(value, ObjectOptions)
        self.syntax = self.base.syntax
        self.text_only = self.base.read_as_text

    def build(self) -> ObjectOptions:
        return replace(self.base, syntax=self.syntax, read_as_text=self.text_only)


class ArrayDraft(OptionsDraft):
    def __init__(self) -> None:
        self.bind(ArrayOptions())

    def bind(self, value: ImportOptions) -> None:
        self.base = option(value, ArrayOptions)
        self.archive = self.base.archive
        self.header_bytes = self.base.max_header_bytes
        self.record_table = self.base.record_table

    def build(self) -> ArrayOptions:
        return replace(
            self.base,
            archive=self.archive,
            max_header_bytes=self.header_bytes,
            record_table=self.record_table,
        )


class CheckpointDraft(OptionsDraft):
    def __init__(self) -> None:
        self.bind(CheckpointOptions())

    def bind(self, value: ImportOptions) -> None:
        self.base = option(value, CheckpointOptions)
        self.nodes, self.depth = self.base.max_nodes, self.base.max_depth

    def build(self) -> CheckpointOptions:
        return replace(self.base, max_nodes=self.nodes, max_depth=self.depth)
