"""Native multi-file/folder picker rendered from worker-prepared listings."""

from concurrent.futures import Executor, Future
from pathlib import Path

from imgui_bundle import imgui

from datelier.core.jobs import JobExecutor
from datelier.io.catalog import DirectoryListing, list_directory


class FileBrowser:
    def __init__(self, executor: Executor, directory: Path) -> None:
        self._executor = JobExecutor(executor, max_workers=1, name="browser")
        self._future: Future[DirectoryListing] | None = None
        self.listing: DirectoryListing | None = None
        self.path = str(directory)
        self.selected: set[Path] = set()
        self.owner: str | None = None
        self.folder_mode = False
        self._open_popup = False
        self.visible = False
        self.message = ""
        self.row_pixels: dict[Path, tuple[float, float]] = {}
        self.open_pixel: tuple[float, float] = (0, 0)
        self.all_pixel: tuple[float, float] = (0, 0)

    @property
    def busy(self) -> bool:
        return self._future is not None

    def open(self, owner: str, *, folder: bool = False) -> None:
        self.owner = owner
        self.folder_mode = folder
        self.visible = self._open_popup = True
        self.selected.clear()
        self.request_directory(Path(self.path))

    def request_directory(self, path: Path) -> None:
        if self._future is not None:
            self._future.cancel()
        self._future = self._executor.submit(list_directory, path)
        self.message = "Listing supported tabular files…"

    def poll(self) -> None:
        future = self._future
        if future is None or not future.done():
            return
        self._future = None
        try:
            self.listing = future.result()
            self.path = str(self.listing.directory)
            self.message = f"{len(self.listing.files)} supported tabular files."
        except Exception as error:
            self.listing = None
            self.message = (
                f"Could not list folder: {error}. Choose another folder or retry."
            )

    def cancel(self) -> None:
        if self._future is not None:
            self._future.cancel()
        self._future = None
        self.visible = self._open_popup = False
        self.owner = None
        self.selected.clear()

    def show(self) -> tuple[Path, ...] | None:
        if self._open_popup:
            imgui.open_popup("Open files or folder")
            self._open_popup = False
        if not self.visible:
            if imgui.is_popup_open("Open files or folder"):
                opened, _ = imgui.begin_popup_modal("Open files or folder")
                if opened:
                    imgui.close_current_popup()
                    imgui.end_popup()
            return None
        imgui.set_next_window_size(imgui.ImVec2(680, 500), imgui.Cond_.appearing)
        opened, visible = imgui.begin_popup_modal("Open files or folder", self.visible)
        if visible is False:
            self.cancel()
        if not opened:
            return None
        result: tuple[Path, ...] | None = None
        _, self.path = imgui.input_text("Folder", self.path)
        if imgui.button("Go / retry folder"):
            self.request_directory(Path(self.path))
        imgui.same_line()
        if imgui.button("Parent folder"):
            self.request_directory(Path(self.path).parent)
        imgui.text_wrapped(self.message)
        if self.selected:
            imgui.text(f"{len(self.selected)} files selected across folders")
        if imgui.begin_child("Source listing", imgui.ImVec2(0, -65)):
            self.row_pixels.clear()
            listing = self.listing
            if listing is not None and not self.busy:
                entries = [*listing.folders, *listing.files]
                clipper = imgui.ListClipper()
                clipper.begin(len(entries), imgui.get_frame_height_with_spacing())
                while clipper.step():
                    for index in range(clipper.display_start, clipper.display_end):
                        entry = entries[index]
                        if isinstance(entry, Path):
                            if imgui.selectable(
                                f"[Folder] {entry.name}##{entry}",
                                False,
                                size=imgui.ImVec2(0, imgui.get_frame_height()),
                            )[0]:
                                self.request_directory(entry)
                        else:
                            clicked, checked = imgui.checkbox(
                                f"{entry.name} · {entry.format}##{entry.path}",
                                entry.path in self.selected,
                            )
                            lo, hi = (
                                imgui.get_item_rect_min(),
                                imgui.get_item_rect_max(),
                            )
                            self.row_pixels[entry.path] = (
                                (lo.x + hi.x) / 2,
                                (lo.y + hi.y) / 2,
                            )
                            if clicked:
                                if checked:
                                    self.selected.add(entry.path)
                                else:
                                    self.selected.discard(entry.path)
                for diagnostic in listing.diagnostics:
                    imgui.text_wrapped(diagnostic)
        imgui.end_child()
        imgui.begin_disabled(not self.selected or self.busy)
        if imgui.button("Open selected files"):
            result = tuple(sorted(self.selected))
        lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        self.open_pixel = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)
        imgui.end_disabled()
        if self.folder_mode:
            imgui.same_line()
            imgui.begin_disabled(
                self.busy or self.listing is None or not self.listing.files
            )
            if imgui.button("Open all files in folder"):
                assert self.listing is not None
                result = tuple(file.path for file in self.listing.files)
            lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
            self.all_pixel = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)
            imgui.end_disabled()
        imgui.same_line()
        if imgui.button("Cancel"):
            self.cancel()
        if result is not None or not self.visible:
            self.visible = False
            imgui.close_current_popup()
        imgui.end_popup()
        return result

    def close(self) -> None:
        self.cancel()
        self._executor.shutdown(wait=False, cancel_futures=True)
