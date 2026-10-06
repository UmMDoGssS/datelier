"""File-owned named record sessions sharing immutable object source data."""

from concurrent.futures import Executor
from dataclasses import replace
from typing import TYPE_CHECKING

from datelier.inspection.arrays.mapping import ArrayRecordMapping
from datelier.inspection.objects.types import NodePath, node_label
from datelier.io.arrays.records import prepare_array_records
from datelier.io.loading import DatasetLoader, LoadPhase
from datelier.io.objects import object_record_view
from datelier.io.types import ArrayOptions, ImportFormat, ImportResult, ObjectOptions

if TYPE_CHECKING:
    from datelier.gui.file_session import FileSession


class RecordViews:
    def __init__(self, executor: Executor | None = None) -> None:
        self.executor = executor
        self.files: list[FileSession] = []
        self.pending: list[FileSession] = []
        self._origins: dict[str, int] = {}
        self.active_id: str | None = None
        self.path: NodePath = ()
        self.focus_path: NodePath = ()
        self.expanded: set[NodePath] = {()}
        self.offsets: dict[NodePath, int] = {}
        self.message = ""

    def active(self, owner: FileSession) -> FileSession:
        return next((f for f in self.files if f.identity == self.active_id), owner)

    def open(
        self, owner: FileSession, path: NodePath, *, as_text: bool = False
    ) -> FileSession:
        from datelier.gui.file_session import FileSession

        active = owner.loader.active
        if owner.closed or active is None or active.imported.object_root is None:
            raise ValueError("Open a structured source before extracting records")
        root, source = active.imported.object_root, active.dataset.source
        imported_options = active.imported.options
        assert isinstance(imported_options, ObjectOptions)
        options = ObjectOptions(imported_options.syntax, path, as_text)
        for file in self.pending:
            if file.controls.options(ImportFormat.OBJECT) == options:
                return file
        for file in self.files:
            if file.loader.active and file.loader.active.imported.options == options:
                self.active_id = file.identity
                return file
        if len(self.files) + len(self.pending) >= 32:
            raise ValueError("Close a record view before opening more than 32 views")

        def extract(_path: object, _options: object) -> ImportResult:
            return object_record_view(root, source, options)

        file = FileSession.create(
            owner.preferences,
            executor=self.executor,
            loader_override=DatasetLoader(extract, executor=self.executor),
        )
        file.view_name = node_label(path)
        file.controls.bind_settings(ImportFormat.OBJECT, options)
        file.loader.request(source.path)
        self.pending.append(file)
        self._origins[file.identity] = owner.loader.generation
        return file

    def open_array(
        self, owner: FileSession, mapping: ArrayRecordMapping
    ) -> FileSession:
        from datelier.gui.file_session import FileSession

        active = owner.loader.active
        if owner.closed or active is None or active.imported.array_catalog is None:
            raise ValueError("Open array metadata before confirming a record mapping")
        imported = active.imported
        catalog = imported.array_catalog
        assert catalog is not None and isinstance(imported.options, ArrayOptions)
        mapping.record_count(catalog)
        options = replace(imported.options, mapping=mapping)
        for file in (*self.pending, *self.files):
            if file.controls.options(ImportFormat.ARRAY) == options:
                if file in self.files:
                    self.active_id = file.identity
                return file
        if len(self.files) + len(self.pending) >= 32:
            raise ValueError("Close a record view before opening more than 32 views")
        store = owner.arrays.store

        def extract(_path: object, _options: object) -> ImportResult:
            dataset, diagnostics = prepare_array_records(store, catalog, mapping)
            store.check_source(catalog)
            return replace(
                imported, dataset=dataset, options=options, diagnostics=diagnostics
            )

        file = FileSession.create(
            owner.preferences,
            executor=self.executor,
            array_store=store,
            loader_override=DatasetLoader(extract, executor=self.executor),
        )
        file.view_name = (
            f"{mapping.member} · {mapping.layout} · axis {mapping.record_axis}"
        )
        file.controls.bind_settings(ImportFormat.ARRAY, options)
        file.loader.request(active.dataset.source.path)
        self.pending.append(file)
        self._origins[file.identity] = owner.loader.generation
        return file

    def poll(self, owner: FileSession) -> None:
        for file in self.files:
            file.poll()
        for file in tuple(self.pending):
            if self._origins[file.identity] != owner.loader.generation:
                file.close()
                self.pending.remove(file)
                self._origins.pop(file.identity)
                self.message = "Source request changed; obsolete extraction abandoned."
                continue
            file.poll()
            if file.loader.active is not None:
                self.files.append(file)
                self.active_id = file.identity
                self.pending.remove(file)
                self._origins.pop(file.identity)
                self.message = f"Opened {file.view_name}"
            elif file.loader.status.phase == LoadPhase.FAILED:
                self.message = file.loader.status.message
                self.pending.remove(file)
                self._origins.pop(file.identity)
                file.close()

    def close_view(self, identity: str) -> None:
        for file in tuple(self.files):
            if file.identity == identity:
                file.close()
                self.files.remove(file)
        if self.active_id == identity:
            self.active_id = None

    def clear(self) -> None:
        for file in (*self.files, *self.pending):
            file.close()
        self.files.clear()
        self.pending.clear()
        self._origins.clear()
        self.active_id = None
        self.path = ()
        self.focus_path = ()
        self.expanded = {()}
        self.offsets.clear()
        self.message = ""
