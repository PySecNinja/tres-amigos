"""Textual-based UI for Pomodoro timer."""

from pathlib import Path
from textual.app import App, ComposeResult
from textual.widgets import Static, Footer, ProgressBar, Label
from textual.containers import Container, Vertical, Center
from textual.binding import Binding
from textual.timer import Timer

from .scheduler import PomodoroTimer, Phase, Status


# Big digit representations (7 lines tall, 6 chars wide)
BIG_DIGITS = {
    "0": [
        " ████ ",
        "██  ██",
        "██  ██",
        "██  ██",
        "██  ██",
        "██  ██",
        " ████ ",
    ],
    "1": [
        "  ██  ",
        " ███  ",
        "  ██  ",
        "  ██  ",
        "  ██  ",
        "  ██  ",
        " ████ ",
    ],
    "2": [
        " ████ ",
        "██  ██",
        "    ██",
        "  ██  ",
        " ██   ",
        "██    ",
        "██████",
    ],
    "3": [
        " ████ ",
        "██  ██",
        "    ██",
        "  ███ ",
        "    ██",
        "██  ██",
        " ████ ",
    ],
    "4": [
        "██  ██",
        "██  ██",
        "██  ██",
        "██████",
        "    ██",
        "    ██",
        "    ██",
    ],
    "5": [
        "██████",
        "██    ",
        "██    ",
        "█████ ",
        "    ██",
        "██  ██",
        " ████ ",
    ],
    "6": [
        " ████ ",
        "██    ",
        "██    ",
        "█████ ",
        "██  ██",
        "██  ██",
        " ████ ",
    ],
    "7": [
        "██████",
        "    ██",
        "   ██ ",
        "  ██  ",
        "  ██  ",
        "  ██  ",
        "  ██  ",
    ],
    "8": [
        " ████ ",
        "██  ██",
        "██  ██",
        " ████ ",
        "██  ██",
        "██  ██",
        " ████ ",
    ],
    "9": [
        " ████ ",
        "██  ██",
        "██  ██",
        " █████",
        "    ██",
        "    ██",
        " ████ ",
    ],
    ":": [
        "      ",
        "  ██  ",
        "  ██  ",
        "      ",
        "  ██  ",
        "  ██  ",
        "      ",
    ],
}


def render_big_time(seconds: int) -> str:
    """Render time as big ASCII digits."""
    mins = seconds // 60
    secs = seconds % 60
    time_str = f"{mins:02d}:{secs:02d}"

    lines = []
    for line_num in range(7):
        line_parts = []
        for char in time_str:
            if char in BIG_DIGITS:
                line_parts.append(BIG_DIGITS[char][line_num])
            else:
                line_parts.append("      ")
        lines.append(" ".join(line_parts))

    return "\n".join(lines)


class BigTimer(Static):
    """Big ASCII timer display."""

    def __init__(self, timer: PomodoroTimer) -> None:
        super().__init__()
        self.pomo_timer = timer

    def on_mount(self) -> None:
        self.update_display()

    def update_display(self) -> None:
        self.update(render_big_time(self.pomo_timer.remaining_seconds))


class PhaseLabel(Static):
    """Phase label with cycle counter."""

    def __init__(self, timer: PomodoroTimer) -> None:
        super().__init__()
        self.pomo_timer = timer

    def on_mount(self) -> None:
        self.update_display()

    def update_display(self) -> None:
        text = f"─── {self.pomo_timer.phase_label} {self.pomo_timer.cycle_display} ───"
        self.update(text)


class StatusBadge(Static):
    """Status indicator badge."""

    def __init__(self, timer: PomodoroTimer) -> None:
        super().__init__()
        self.pomo_timer = timer

    def on_mount(self) -> None:
        self.update_display()

    def update_display(self) -> None:
        if self.pomo_timer.status == Status.RUNNING:
            self.update("▶ RUNNING")
            self.remove_class("paused")
            self.add_class("running")
        else:
            self.update("⏸ PAUSED")
            self.remove_class("running")
            self.add_class("paused")


class PomodoroApp(App):
    """Pomodoro timer application."""

    CSS_PATH = "pomodoro.tcss"

    BINDINGS = [
        Binding("space", "toggle", "Start/Pause"),
        Binding("r", "reset", "Reset"),
        Binding("n", "next", "Next"),
        Binding("p", "prev", "Previous"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        timer: PomodoroTimer,
        notify_enabled: bool = True,
        on_phase_complete=None,
    ) -> None:
        super().__init__()
        self.pomo_timer = timer
        self.notify_enabled = notify_enabled
        self.on_phase_complete_callback = on_phase_complete
        self._tick_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        with Container(id="main"):
            with Vertical(id="timer-container"):
                yield PhaseLabel(self.pomo_timer, id="phase-label")
                yield BigTimer(self.pomo_timer, id="big-timer")
                yield StatusBadge(self.pomo_timer, id="status-badge")
                yield ProgressBar(id="progress", show_eta=False, show_percentage=False)
        yield Footer()

    def on_mount(self) -> None:
        self._update_phase_class()
        self._update_progress()
        self._tick_timer = self.set_interval(1.0, self._tick)

    def _tick(self) -> None:
        """Called every second."""
        old_phase = self.pomo_timer.phase
        completed = self.pomo_timer.tick()

        self._refresh_display()

        if completed and self.on_phase_complete_callback:
            self.on_phase_complete_callback(old_phase, self.pomo_timer.phase)

    def _refresh_display(self) -> None:
        """Update all display elements."""
        self.query_one("#big-timer", BigTimer).update_display()
        self.query_one("#phase-label", PhaseLabel).update_display()
        self.query_one("#status-badge", StatusBadge).update_display()
        self._update_progress()
        self._update_phase_class()

    def _update_progress(self) -> None:
        """Update the progress bar."""
        progress_bar = self.query_one("#progress", ProgressBar)
        progress_bar.update(total=100, progress=self.pomo_timer.progress * 100)

    def _update_phase_class(self) -> None:
        """Update CSS class based on current phase."""
        container = self.query_one("#timer-container")
        container.remove_class("work", "short-break", "long-break")

        if self.pomo_timer.phase == Phase.WORK:
            container.add_class("work")
        elif self.pomo_timer.phase == Phase.SHORT_BREAK:
            container.add_class("short-break")
        else:
            container.add_class("long-break")

    def action_toggle(self) -> None:
        """Toggle timer start/pause."""
        self.pomo_timer.toggle()
        self._refresh_display()

    def action_reset(self) -> None:
        """Reset current phase."""
        self.pomo_timer.reset()
        self._refresh_display()

    def action_next(self) -> None:
        """Skip to next phase."""
        old_phase = self.pomo_timer.phase
        self.pomo_timer.next_phase()
        self._refresh_display()
        if self.on_phase_complete_callback:
            self.on_phase_complete_callback(old_phase, self.pomo_timer.phase)

    def action_prev(self) -> None:
        """Go to previous phase."""
        self.pomo_timer.prev_phase()
        self._refresh_display()


def run_ui(timer: PomodoroTimer, notify_enabled: bool = True, on_phase_complete=None) -> None:
    """Run the Pomodoro UI.

    Args:
        timer: The timer instance.
        notify_enabled: Whether notifications are enabled.
        on_phase_complete: Callback for phase completion.
    """
    app = PomodoroApp(timer, notify_enabled, on_phase_complete)
    app.run()
