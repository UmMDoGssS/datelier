"""Compact fields with captions above their controls."""

from imgui_bundle import imgui


def combo(label: str, index: int, choices: list[str]) -> tuple[bool, int]:
    imgui.text(label)
    imgui.set_next_item_width(-1)
    return imgui.combo("##" + label, index, choices)


def field(label: str) -> str:
    imgui.text(label)
    imgui.set_next_item_width(-1)
    return "##" + label
