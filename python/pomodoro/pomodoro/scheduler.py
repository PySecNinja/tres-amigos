"""Pure logic for Pomodoro timer state machine."""

from enum import Enum, auto
from typing import Callable, Optional


class Phase(Enum):
    """Timer phase types."""
    WORK = auto()
    SHORT_BREAK = auto()
    LONG_BREAK = auto()


class Status(Enum):
    """Timer running status."""
    RUNNING = auto()
    PAUSED = auto()


class PomodoroTimer:
    """Pomodoro timer state machine.

    Manages phase transitions, timing, and auto-start behavior.
    """

    def __init__(
        self,
        work_mins: int = 25,
        short_mins: int = 5,
        long_mins: int = 15,
        cycle_size: int = 4,
        auto_break: bool = True,
        auto_work: bool = False,
        on_phase_complete: Optional[Callable[[Phase, Phase], None]] = None,
    ):
        """Initialize the timer.

        Args:
            work_mins: Duration of work phase in minutes.
            short_mins: Duration of short break in minutes.
            long_mins: Duration of long break in minutes.
            cycle_size: Number of work phases before a long break.
            auto_break: Auto-start breaks when work ends.
            auto_work: Auto-start work when break ends.
            on_phase_complete: Callback(old_phase, new_phase) when phase ends.
        """
        self.work_secs = work_mins * 60
        self.short_secs = short_mins * 60
        self.long_secs = long_mins * 60
        self.cycle_size = cycle_size
        self.auto_break = auto_break
        self.auto_work = auto_work
        self.on_phase_complete = on_phase_complete

        self._phase = Phase.WORK
        self._status = Status.PAUSED
        self._remaining = self.work_secs
        self._completed_in_cycle = 0  # Work phases completed in current cycle

    @property
    def phase(self) -> Phase:
        """Current phase."""
        return self._phase

    @property
    def status(self) -> Status:
        """Current status (RUNNING or PAUSED)."""
        return self._status

    @property
    def remaining_seconds(self) -> int:
        """Seconds remaining in current phase."""
        return self._remaining

    @property
    def completed_in_cycle(self) -> int:
        """Number of work phases completed in current cycle."""
        return self._completed_in_cycle

    @property
    def total_duration(self) -> int:
        """Total duration of current phase in seconds."""
        if self._phase == Phase.WORK:
            return self.work_secs
        elif self._phase == Phase.SHORT_BREAK:
            return self.short_secs
        else:
            return self.long_secs

    @property
    def progress(self) -> float:
        """Progress through current phase (0.0 to 1.0)."""
        total = self.total_duration
        if total == 0:
            return 1.0
        return 1.0 - (self._remaining / total)

    @property
    def phase_label(self) -> str:
        """Human-readable phase label."""
        labels = {
            Phase.WORK: "Pomodoro",
            Phase.SHORT_BREAK: "Short Break",
            Phase.LONG_BREAK: "Long Break",
        }
        return labels[self._phase]

    @property
    def status_label(self) -> str:
        """Human-readable status label."""
        return "RUNNING" if self._status == Status.RUNNING else "PAUSED"

    @property
    def cycle_display(self) -> str:
        """Display string for cycle counter (e.g., 'Pomodoro 2/4')."""
        if self._phase == Phase.WORK:
            current = self._completed_in_cycle + 1
        else:
            current = self._completed_in_cycle
        return f"{current}/{self.cycle_size}"

    def start(self) -> None:
        """Start the timer."""
        self._status = Status.RUNNING

    def pause(self) -> None:
        """Pause the timer."""
        self._status = Status.PAUSED

    def toggle(self) -> None:
        """Toggle between running and paused."""
        if self._status == Status.RUNNING:
            self.pause()
        else:
            self.start()

    def reset(self) -> None:
        """Reset current phase to full duration."""
        self._remaining = self.total_duration
        self._status = Status.PAUSED

    def _get_duration_for_phase(self, phase: Phase) -> int:
        """Get duration in seconds for a given phase."""
        if phase == Phase.WORK:
            return self.work_secs
        elif phase == Phase.SHORT_BREAK:
            return self.short_secs
        else:
            return self.long_secs

    def _determine_next_phase(self) -> Phase:
        """Determine the next phase based on current state."""
        if self._phase == Phase.WORK:
            # After work, check if we need a long break
            completed = self._completed_in_cycle + 1
            if completed >= self.cycle_size:
                return Phase.LONG_BREAK
            else:
                return Phase.SHORT_BREAK
        else:
            # After any break, go to work
            return Phase.WORK

    def _determine_prev_phase(self) -> Phase:
        """Determine the previous phase based on current state."""
        if self._phase == Phase.WORK:
            # Before work was either a break
            if self._completed_in_cycle == 0:
                # First work of cycle, previous was long break
                return Phase.LONG_BREAK
            else:
                return Phase.SHORT_BREAK
        elif self._phase == Phase.SHORT_BREAK:
            return Phase.WORK
        else:  # LONG_BREAK
            return Phase.WORK

    def next_phase(self) -> None:
        """Skip to the next phase."""
        old_phase = self._phase
        new_phase = self._determine_next_phase()

        # Update cycle counter if completing a work phase
        if old_phase == Phase.WORK:
            self._completed_in_cycle += 1
            if self._completed_in_cycle >= self.cycle_size:
                self._completed_in_cycle = 0

        self._phase = new_phase
        self._remaining = self._get_duration_for_phase(new_phase)

        # Determine auto-start behavior
        should_auto = False
        if new_phase == Phase.WORK:
            should_auto = self.auto_work
        else:
            should_auto = self.auto_break

        if should_auto:
            self._status = Status.RUNNING
        else:
            self._status = Status.PAUSED

        if self.on_phase_complete:
            self.on_phase_complete(old_phase, new_phase)

    def prev_phase(self) -> None:
        """Go back to the previous phase."""
        old_phase = self._phase
        new_phase = self._determine_prev_phase()

        # Adjust cycle counter
        if old_phase == Phase.WORK and self._completed_in_cycle > 0:
            # Going back from work to break means undoing a completed work
            pass  # Don't decrement, we're going back to a break
        elif old_phase in (Phase.SHORT_BREAK, Phase.LONG_BREAK):
            # Going back from break to work
            if self._completed_in_cycle > 0:
                self._completed_in_cycle -= 1
            elif old_phase == Phase.LONG_BREAK:
                # Going back from long break to last work of previous cycle
                self._completed_in_cycle = self.cycle_size - 1

        self._phase = new_phase
        self._remaining = self._get_duration_for_phase(new_phase)
        self._status = Status.PAUSED

    def tick(self) -> bool:
        """Decrement timer by one second if running.

        Returns:
            True if phase completed, False otherwise.
        """
        if self._status != Status.RUNNING:
            return False

        if self._remaining > 0:
            self._remaining -= 1

        if self._remaining == 0:
            self.next_phase()
            return True

        return False
