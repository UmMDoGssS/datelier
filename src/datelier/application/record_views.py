"""Independent named record controllers sharing immutable source metadata/caches."""

from concurrent.futures import Executor
from dataclasses import replace
from typing import TYPE_CHECKING

from datelier.inspection.arrays.mapping import ArrayRecordMapping
from datelier.inspection.audio.playback.controller import AudioPlayback
from datelier.inspection.objects.types import NodePath, node_label
from datelier.io.arrays.records import prepare_array_records
from datelier.io.loading import DatasetLoader, LoadPhase
from datelier.io.objects import object_record_view
from datelier.io.types import (
    ArrayOptions,
    ImportFormat,
    ImportOptions,
    ImportResult,
    ObjectOptions,
)

if TYPE_CHECKING:
    from datelier.application.file import FileController


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

    def active(self, owner: FileController) -> FileController:
        return next((f for f in self.files if f.identity == self.active_id), owner)

    def open(
        self, owner: FileController, path: NodePath, *, as_text: bool = False
    ) -> None:
        from datelier.application.file import FileController

        active = owner.inspection
        if active is None or active.imported.object_root is None:
            raise ValueError("Open a structured source before extracting records")
        original = active.imported.options
        assert isinstance(original, ObjectOptions)
        options = ObjectOptions(original.syntax, path, as_text)
        for file in (*self.files, *self.pending):
            if file.inspection and file.inspection.imported.options == options:
                self.active_id = file.identity
                return
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

    def open_array(self, owner: FileController, mapping: ArrayRecordMapping) -> None:
        from datelier.application.file import FileController

        active = owner.inspection
        if active is None or active.imported.array_catalog is None:
            raise ValueError("Open array metadata before confirming a record mapping")
        imported = active.imported
        catalog = imported.array_catalog
        assert catalog is not None and isinstance(imported.options, ArrayOptions)
        options = replace(imported.options, mapping=mapping)
        mapping.record_count(catalog)
        for file in self.files:
            if file.inspection and file.inspection.imported.options == options:
                self.active_id = file.identity
                return

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
        file.loader.request(
            active.dataset.source.path, options, format=ImportFormat.ARRAY
        )
        self.pending.append(file)
        self._origins[file.identity] = owner.loader.generation

    def poll(self, owner: FileController) -> None:
        for file in self.files:
            file.poll()
        for file in tuple(self.pending):
            if owner.loader.generation != self._origins[file.identity]:
                file.close()
                self.pending.remove(file)
                self._origins.pop(file.identity)
                continue
            file.poll()
            if file.inspection:
                self.pending.remove(file)
                self._origins.pop(file.identity)
                self.files.append(file)
                self.active_id = file.identity
            elif file.loader.status.phase == LoadPhase.FAILED:
                self.message = file.loader.status.message
                self.pending.remove(file)
                self._origins.pop(file.identity)
                file.close()

    def close_view(self, identity: str) -> None:
        file = next((f for f in self.files if f.identity == identity), None)
        if file:
            self.files.remove(file)
            file.close()
        if self.active_id == identity:
            self.active_id = None

    def clear(self) -> None:
        for file in (*self.files, *self.pending):
            file.close()
        self.files.clear()
        self.pending.clear()
        self._origins.clear()
        self.active_id = None
        self.expanded = {()}

    def close(self) -> None:
        self.clear()
