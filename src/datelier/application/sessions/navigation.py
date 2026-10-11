"""Canvas navigation is explicit and independent of background job completion."""

from dataclasses import dataclass


@dataclass
class WorkbenchNavigation:
    comparing: bool = False
    context_tab: str = "View"
    context_open: bool = False

    def activate_file(self) -> None:
        self.comparing = False

    def choose_canvas(self, comparison: bool) -> None:
        self.comparing = comparison
