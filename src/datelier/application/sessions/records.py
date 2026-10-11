"""Independent named record controllers sharing immutable source metadata/caches."""

from concurrent.futures import Executor
from dataclasses import replace
from typing import TYPE_CHECKING

from datelier.inspection.arrays import ArrayRecordMapping
from datelier.inspection.audio.playback.controller import AudioPlayback
from datelier.inspection.objects import NodePath, node_label
from datelier.io.arrays.records import prepare_array_records
from datelier.io.jobs import DatasetLoader, LoadPhase
from datelier.io.objects import object_record_view
from datelier.io.types import (
    ArrayOptions,
    ImportFormat,
    ImportOptions,
    ImportResult,
    ObjectOptions,
)

if TYPE_CHECKING:
    from datelier.application.sessions.file import FileController


class RecordViews:
    def __init__(self, executor: Executor, playback: AudioPlayback) -> None:
        self.executor, self.playback = executor, playback
        self.files: list[FileController] = []
        self.pending: list[FileController] = []
        self.active_id: str | None = None
        self.path: NodePath = ()
        self.focus_path: NodePath = ()
        self.expanded: set[NodePath] = {()}
        self.message = ""
        self._origins: dict[str, int] = {}
        self._options: dict[str, ImportOptions] = {}
        self._previous: dict[str, str | None] = {}

    def active(self, owner: FileController) -> FileController:
        return next(
            (f for f in (*self.files, *self.pending) if f.identity == self.active_id),
            owner,
        )

    def choose(self, identity: str | None) -> None:
        if identity is not None and not any(
            f.identity == identity for f in (*self.files, *self.pending)
        ):
            raise ValueError("The record view is unavailable")
        self.active_id = identity

    def open(
        self, owner: FileController, path: NodePath, *, as_text: bool = False
    ) -> FileController:
        from datelier.application.sessions.file import FileController

        active = owner.inspection
        if active is None or active.imported.object_root is None:
            raise ValueError("Open a structured source before extracting records")
        original = active.imported.options
        assert isinstance(original, ObjectOptions)
        options = ObjectOptions(original.syntax, path, as_text)
        for file in (*self.files, *self.pending):
            if (
                self._options.get(file.identity) == options
                or file.inspection
                and file.inspection.imported.options == options
            ):
                self.choose(file.identity)
                return file
        if len(self.files) + len(self.pending) >= 32:
            raise ValueError("Close a record view before opening more than 32 views")

        def extract(_path: object, _options: object) -> ImportResult:
            return object_record_view(
                active.imported.object_root, active.dataset.source, options
            )

        file = FileController(
            self.executor,
            loader=DatasetLoader(extract, executor=self.executor),
            playback=self.playback,
        )
        file.view_name = node_label(path)
        file.loader.request(
            active.dataset.source.path, options, format=ImportFormat.OBJECT
        )
        self.pending.append(file)
        self._origins[file.identity] = owner.loader.generation
        self._options[file.identity] = options
        self._previous[file.identity] = self.active_id
        self.choose(file.identity)
        return file

    def open_array(
        self, owner: FileController, mapping: ArrayRecordMapping
    ) -> FileController:
        from datelier.application.sessions.file import FileController

        active = owner.inspection
        if active is None or active.imported.array_catalog is None:
            raise ValueError("Open array metadata before confirming a record mapping")
        imported = active.imported
        catalog = imported.array_catalog
        assert catalog is not None and isinstance(imported.options, ArrayOptions)
        options = replace(imported.options, mapping=mapping)
        mapping.record_count(catalog)
        for file in (*self.files, *self.pending):
            if (
                self._options.get(file.identity) == options
                or file.inspection
                and file.inspection.imported.options == options
            ):
                self.choose(file.identity)
                return file

        if len(self.files) + len(self.pending) >= 32:
            raise ValueError("Close a record view before opening more than 32 views")

        def extract(_path: object, _options: ImportOptions | None) -> ImportResult:
            dataset, diagnostics = prepare_array_records(
                owner.arrays.store, catalog, mapping
            )
            owner.arrays.store.check_source(catalog)
            return replace(
                imported, dataset=dataset, options=options, diagnostics=diagnostics
            )

        file = FileController(
            self.executor,
            loader=DatasetLoader(extract, executor=self.executor),
            array_store=owner.arrays.store,
            playback=self.playback,
        )
        file.view_name = (
            f"{mapping.member} · {mapping.layout} · axis {mapping.record_axis}"
        )
        file.views = replace(file.views, tab="Inspect")
        file.records.settings = replace(file.records.settings, gallery=False)
        file.loader.request(
            active.dataset.source.path, options, format=ImportFormat.ARRAY
        )
        self.pending.append(file)
        self._origins[file.identity] = owner.loader.generation
        self._options[file.identity] = options
        self._previous[file.identity] = self.active_id
        self.choose(file.identity)
        return file

    def poll(self, owner: FileController) -> None:
        for file in self.files:
            file.poll()
        for file in tuple(self.pending):
            if owner.loader.generation != self._origins[file.identity]:
                self.close_view(file.identity)
                continue
            file.poll()
            if file.inspection:
                self.pending.remove(file)
                self._origins.pop(file.identity)
                self.files.append(file)
                self._previous.pop(file.identity, None)
                self.message = f"Record view ready: {file.view_name}"
            elif file.loader.status.phase == LoadPhase.FAILED:
                self.message = file.loader.status.message
                self.close_view(file.identity)

    def close_view(self, identity: str) -> None:
        previous = self._previous.pop(identity, None)
        file = next(
            (f for f in (*self.files, *self.pending) if f.identity == identity), None
        )
        if file:
            collection = self.pending if file in self.pending else self.files
            collection.remove(file)
            self._origins.pop(file.identity, None)
            self._options.pop(file.identity, None)
            file.close()
        if self.active_id == identity:
            self.active_id = (
                previous
                if any(f.identity == previous for f in (*self.files, *self.pending))
                else None
            )

    def clear(self) -> None:
        for file in (*self.files, *self.pending):
            file.close()
        self.files.clear()
        self.pending.clear()
        self._origins.clear()
        self._options.clear()
        self._previous.clear()
        self.path = self.focus_path = ()
        self.active_id = None
        self.expanded = {()}

    def close(self) -> None:
        self.clear()
