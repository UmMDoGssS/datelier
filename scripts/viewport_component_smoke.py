"""Native drag/expand/restore on the shared content viewport."""

import json

from imgui_bundle import hello_imgui, imgui, immapp

from datelier.gui.components.viewport import ResizableViewport


def main() -> None:
    area = ResizableViewport(height=220)
    frame = stage = entered = 0
    expanded = False

    def show() -> None:
        nonlocal frame, stage, entered, expanded
        frame += 1
        imgui.set_next_window_pos((20, 20), imgui.Cond_.always)
        imgui.set_next_window_size((640, 580), imgui.Cond_.always)
        imgui.begin("Viewport input")

        def content(height: float, fit: bool) -> bool:
            imgui.button("Prepared content", (-1, height))
            return True

        area.show_content("Record", "stable record", content)
        imgui.end()
        io = imgui.get_io()
        age = frame - entered
        if stage == 0 and age > 5:
            io.mouse_pos = imgui.ImVec2(*area.resize_pixel)
            io.want_set_mouse_pos = True
            stage, entered = 1, frame
        elif stage == 1 and age > 3:
            io.add_mouse_button_event(0, True)
            stage, entered = 2, frame
        elif stage == 2 and age > 3:
            io.mouse_pos = imgui.ImVec2(area.resize_pixel[0], area.resize_pixel[1] + 25)
            io.want_set_mouse_pos = True
            stage, entered = 3, frame
        elif stage == 3 and age > 1:
            io.add_mouse_button_event(0, False)
            stage, entered = 4, frame
        elif stage == 4 and age > 5:
            assert area.height == 245, area.height
            io.mouse_pos = imgui.ImVec2(*area.expand_pixel)
            io.want_set_mouse_pos = True
            stage, entered = 5, frame
        elif stage == 5 and age > 3:
            io.add_mouse_button_event(0, True)
            stage, entered = 6, frame
        elif stage == 6 and age > 3:
            io.add_mouse_button_event(0, False)
            stage, entered = 7, frame
        elif stage == 7 and age > 5:
            assert area.expanded and area.rendered_height > 245
            expanded = True
            area.expanded = False
            stage, entered = 8, frame
        elif stage == 8 and age > 3:
            assert area.height == area.rendered_height == 245
            hello_imgui.get_runner_params().app_shall_exit = True
        assert frame < 150, (stage, area)

    params = hello_imgui.RunnerParams()
    params.ini_disable = True
    params.app_window_params.window_geometry.size = (900, 700)
    params.callbacks.show_gui = show
    params.fps_idling.enable_idling = False
    immapp.run(params)
    assert stage == 8 and expanded
    print(json.dumps(dict(native_resize=True, expand_restore=True, frames=frame)))


if __name__ == "__main__":
    main()
