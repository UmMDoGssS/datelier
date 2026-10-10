"""Complete text and tokens have separate shared viewports and exact offsets."""

from dataclasses import replace

from imgui_bundle import imgui

from datelier.application.text import TextController
from datelier.gui.components.base import FrameContext
from datelier.gui.components.native import target
from datelier.gui.components.viewport import ResizableViewport, ViewportContent
from datelier.gui.records.base import RecordContent


class OriginalText(ViewportContent):
    def __init__(self, model: TextController) -> None:
        super().__init__("original")
        self.model = model

    def render(self, frame: FrameContext) -> None:
        page = self.model.pages.active
        if page is None:
            imgui.text_wrapped(self.model.pages.message)
            return
        imgui.text(f"Original [{page.start:,}, {page.end:,})")
        if page.selected_span:
            imgui.text_wrapped(
                f"Selected source span {page.selected_span}: {page.selected_source!r}"
            )
        if imgui.begin_child(
            "original",
            (0, self.height),
            imgui.ChildFlags_.borders,
            imgui.WindowFlags_.horizontal_scrollbar,
        ):
            clipper = imgui.ListClipper()
            clipper.begin(len(page.lines))
            while clipper.step():
                for line in page.lines[clipper.display_start : clipper.display_end]:
                    imgui.text_disabled(str(line.start))
                    for run in line.runs:
                        imgui.same_line(0, 0)
                        if run.highlighted:
                            imgui.text_colored((1, 0.8, 0.2, 1), run.text)
                        else:
                            imgui.text_unformatted(run.text)
        imgui.end_child()


class Tokens(ViewportContent):
    def __init__(self, model: TextController) -> None:
        super().__init__("tokens")
        self.model = model

    def render(self, frame: FrameContext) -> None:
        document = self.model.jobs.active
        if document is None:
            return
        viewport = self.model.jobs.settings.viewport
        flags = (
            imgui.TableFlags_.scroll_y
            | imgui.TableFlags_.borders
            | imgui.TableFlags_.row_bg
        )
        if imgui.begin_table("tokens", 5, flags, (-1, self.height)):
            for header in (
                "Index / piece",
                "ID",
                "Original span",
                "Special",
                "Counted",
            ):
                imgui.table_setup_column(header)
            imgui.table_headers_row()
            clipper = imgui.ListClipper()
            clipper.begin(len(document.tokens))
            while clipper.step():
                for index in range(clipper.display_start, clipper.display_end):
                    token = document.tokens[index]
                    imgui.table_next_row()
                    imgui.table_next_column()
                    label = f"{index + 1}: {token.piece[:96]!r}".replace("##", "# #")
                    if imgui.selectable(
                        label + f"###token-{index}", index == viewport.selected_token
                    )[0]:
                        self.model.jobs.settings = replace(
                            self.model.jobs.settings,
                            viewport=replace(
                                viewport,
                                selected_token=index,
                                start=token.start,
                                piece_start=0,
                            ),
                        )
                    target(frame.child(str(index)), "select")
                    for value in (
                        str(token.token_id),
                        f"[{token.start}, {token.end})",
                        str(token.special),
                        str(token.counted),
                    ):
                        imgui.table_next_column()
                        imgui.text_unformatted(value)
            imgui.end_table()


class TextContent(RecordContent):
    def __init__(self, model: TextController) -> None:
        super().__init__("text")
        self.model = model
        self.children = (
            ResizableViewport(
                "original-text",
                OriginalText(model),
                height=160,
                minimum=100,
                read_height=lambda: model.original_height,
                write_height=lambda value: setattr(model, "original_height", value),
            ),
            ResizableViewport(
                "token-list",
                Tokens(model),
                height=200,
                minimum=100,
                read_height=lambda: model.token_height,
                write_height=lambda value: setattr(model, "token_height", value),
            ),
        )

    def render(self, frame: FrameContext) -> None:
        card = self.card
        if card is None or card.primary is None:
            return
        if imgui.button("Inspect text tokens"):
            self.model.request_record(card.primary.name, card.position)
        target(frame, "prepare")
        imgui.text_wrapped(self.model.jobs.message)
        document = self.model.jobs.active
        matches = document and (
            document.document.origin.row_id,
            document.document.origin.column,
        ) == (card.row_id, card.primary.name)
        if not matches:
            imgui.text_wrapped(card.primary.text)
            return
        assert document is not None
        imgui.text(
            f"{len(document.document.text):,} original code points · "
            f"{document.count:,} counted tokens"
        )
        viewport = self.model.jobs.settings.viewport
        if imgui.button("Previous page"):
            viewport = replace(viewport, start=max(0, viewport.start - viewport.count))
        imgui.same_line()
        if imgui.button("Next page"):
            viewport = replace(
                viewport,
                start=min(len(document.document.text), viewport.start + viewport.count),
            )
        imgui.same_line()
        if imgui.button("End of text"):
            viewport = replace(
                viewport, start=max(0, len(document.document.text) - viewport.count)
            )
        target(frame, "end")
        self.model.jobs.settings = replace(self.model.jobs.settings, viewport=viewport)
        super().render(frame)
