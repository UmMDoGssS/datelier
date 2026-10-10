"""Paged original text and a virtual complete token list with source highlights."""

from dataclasses import replace

from imgui_bundle import imgui

from datelier.gui.components.viewport import ResizableViewport
from datelier.inspection.text.page_jobs import TextPageJobs
from datelier.inspection.text.pages import TextPage, TextViewport
from datelier.inspection.text.types import TokenizedDocument


class TextDocumentView:
    def __init__(self) -> None:
        self.area = ResizableViewport(height=160)
        self.token_area = ResizableViewport(height=200)
        self.rendered_tokens = 0
        self.highlighted_span: tuple[int, int] | None = None
        self.token_pixels: dict[int, tuple[float, float]] = {}

    def show(
        self, document: TokenizedDocument, viewport: TextViewport, pages: TextPageJobs
    ) -> TextViewport:
        doc = document.document
        viewport = replace(
            viewport,
            start=min(viewport.start, len(doc.text)),
            selected_token=min(viewport.selected_token, len(document.tokens) - 1),
        )
        imgui.text_wrapped(
            f"{doc.status} · {len(doc.text):,} original code points · "
            f"{document.count:,} counted tokens"
        )
        if doc.diagnostic:
            imgui.text_wrapped(doc.diagnostic)
        if imgui.small_button("Previous text page"):
            viewport = replace(viewport, start=max(0, viewport.start - viewport.count))
        imgui.same_line()
        if imgui.small_button("Next text page"):
            viewport = replace(
                viewport, start=min(len(doc.text), viewport.start + viewport.count)
            )
        imgui.same_line()
        if imgui.small_button("End of text"):
            viewport = replace(viewport, start=max(0, len(doc.text) - viewport.count))
        imgui.set_next_item_width(130)
        changed, start = imgui.input_int("Original offset", viewport.start)
        if changed:
            viewport = replace(viewport, start=max(0, min(start, len(doc.text))))
        imgui.set_next_item_width(130)
        changed, count = imgui.input_int("Code points per page", viewport.count)
        if changed:
            viewport = replace(viewport, count=max(128, min(count, 8192)))
        imgui.set_next_item_width(130)
        changed, index = imgui.input_int(
            "Token index (1-based)", viewport.selected_token + 1
        )
        if changed and document.tokens:
            index = max(0, min(index - 1, len(document.tokens) - 1))
            viewport = replace(
                viewport,
                selected_token=index,
                start=document.tokens[index].start,
                piece_start=0,
            )
        if 0 <= viewport.selected_token < len(document.tokens):
            imgui.set_next_item_width(130)
            changed, offset = imgui.input_int(
                "Token piece offset", viewport.piece_start
            )
            if changed:
                viewport = replace(
                    viewport,
                    piece_start=max(
                        0,
                        min(
                            offset, len(document.tokens[viewport.selected_token].piece)
                        ),
                    ),
                )
        pages.sync(document, viewport)
        page = pages.active
        if page is not None:
            self.area.show_content(
                "Original text",
                document.document.origin,
                lambda height, fit: self._text(page, height),
                minimum_height=100,
            )
        else:
            imgui.text_wrapped(pages.message)

        def tokens(height: float, fit: bool) -> bool:
            nonlocal viewport
            viewport = self._tokens(document, viewport, height)
            return True

        self.token_area.show_content(
            "Tokens", document.document.origin, tokens, minimum_height=100
        )
        return viewport

    def _text(self, page: TextPage, height: float) -> bool:
        imgui.text(
            f"Original [{page.start:,}, {page.end:,}); "
            "control characters use visible symbols."
        )
        self.highlighted_span = page.selected_span
        if page.selected_span is not None:
            a, b = page.selected_span
            imgui.text_wrapped(
                f"Token piece [{page.piece_start}, "
                f"{page.piece_start + len(page.selected_piece)}) / "
                f"{page.piece_length}: {page.selected_piece!r}"
            )
            imgui.text_wrapped(
                f"Selected original span [{a}, {b}): {page.selected_source!r}"
                + (" … (first 256 code points)" if b - a > 256 else "")
            )
            if a == b:
                imgui.text("This token has no original source span.")
        if imgui.begin_child(
            "Original full text",
            (0, height),
            imgui.ChildFlags_.borders,
            imgui.WindowFlags_.horizontal_scrollbar,
        ):
            clipper = imgui.ListClipper()
            clipper.begin(len(page.lines))
            while clipper.step():
                for index in range(clipper.display_start, clipper.display_end):
                    line = page.lines[index]
                    imgui.text_disabled(f"{line.start:>8}")
                    for run in line.runs:
                        imgui.same_line(0, 0)
                        if run.highlighted:
                            imgui.text_colored((1, 0.8, 0.2, 1), run.text)
                            lo, hi = (
                                imgui.get_item_rect_min(),
                                imgui.get_item_rect_max(),
                            )
                            imgui.get_window_draw_list().add_line(
                                (lo.x, hi.y), (hi.x, hi.y), 0xFF33CCFF, 2
                            )
                        else:
                            imgui.text_unformatted(run.text)
        imgui.end_child()
        return True

    def _tokens(
        self, document: TokenizedDocument, viewport: TextViewport, height: float
    ) -> TextViewport:
        self.rendered_tokens = 0
        self.token_pixels.clear()
        flags = (
            imgui.TableFlags_.scroll_y
            | imgui.TableFlags_.borders
            | imgui.TableFlags_.row_bg
        )
        if imgui.begin_table("Complete tokens", 5, flags, (-1, height)):
            for name in (
                "Index / piece",
                "ID",
                "Original offsets",
                "Special",
                "Counted",
            ):
                imgui.table_setup_column(name)
            imgui.table_headers_row()
            clipper = imgui.ListClipper()
            clipper.begin(len(document.tokens))
            if 0 <= viewport.selected_token < len(document.tokens):
                clipper.include_item_by_index(viewport.selected_token)
            while clipper.step():
                for index in range(clipper.display_start, clipper.display_end):
                    token = document.tokens[index]
                    self.rendered_tokens += 1
                    imgui.table_next_row()
                    imgui.table_next_column()
                    label = f"{index + 1}: {token.piece[:96]!r}".replace("##", "# #")
                    if len(token.piece) > 96:
                        label += "…"
                    if imgui.selectable(
                        f"{label}###token{index}", index == viewport.selected_token
                    )[0]:
                        viewport = replace(
                            viewport,
                            selected_token=index,
                            start=token.start,
                            piece_start=0,
                        )
                    lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
                    self.token_pixels[index] = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)
                    for value in (
                        str(token.token_id) if token.token_id is not None else "—",
                        f"[{token.start}, {token.end})",
                        str(token.special),
                        str(token.counted),
                    ):
                        imgui.table_next_column()
                        imgui.text_unformatted(value)
            imgui.end_table()
        return viewport
