"""Unit tests for scheduler.py."""

import pytest
from pomodoro.scheduler import PomodoroTimer, Phase, Status


class TestPomodoroTimerBasics:
    """Test basic timer functionality."""

    def test_initial_state(self):
        """Timer starts paused in work phase."""
        timer = PomodoroTimer()
        assert timer.phase == Phase.WORK
        assert timer.status == Status.PAUSED
        assert timer.remaining_seconds == 25 * 60
        assert timer.completed_in_cycle == 0

    def test_custom_durations(self):
        """Timer respects custom durations."""
        timer = PomodoroTimer(work_mins=10, short_mins=2, long_mins=5)
        assert timer.remaining_seconds == 10 * 60
        assert timer.work_secs == 10 * 60
        assert timer.short_secs == 2 * 60
        assert timer.long_secs == 5 * 60

    def test_start_pause_toggle(self):
        """Start, pause, and toggle work correctly."""
        timer = PomodoroTimer()
        assert timer.status == Status.PAUSED

        timer.start()
        assert timer.status == Status.RUNNING

        timer.pause()
        assert timer.status == Status.PAUSED

        timer.toggle()
        assert timer.status == Status.RUNNING

        timer.toggle()
        assert timer.status == Status.PAUSED


class TestTick:
    """Test tick countdown behavior."""

    def test_tick_decrements(self):
        """Tick decrements remaining seconds when running."""
        timer = PomodoroTimer(work_mins=1)
        timer.start()

        initial = timer.remaining_seconds
        timer.tick()
        assert timer.remaining_seconds == initial - 1

    def test_tick_does_nothing_when_paused(self):
        """Tick does nothing when paused."""
        timer = PomodoroTimer()
        initial = timer.remaining_seconds
        timer.tick()
        assert timer.remaining_seconds == initial

    def test_tick_triggers_phase_change_at_zero(self):
        """Tick triggers phase change when reaching zero."""
        timer = PomodoroTimer(work_mins=1, auto_break=False)
        timer._remaining = 1
        timer.start()

        completed = timer.tick()
        assert completed is True
        assert timer.phase == Phase.SHORT_BREAK


class TestReset:
    """Test reset behavior."""

    def test_reset_restores_full_duration(self):
        """Reset restores phase to full duration."""
        timer = PomodoroTimer(work_mins=25)
        timer.start()
        for _ in range(100):
            timer.tick()

        timer.reset()
        assert timer.remaining_seconds == 25 * 60
        assert timer.status == Status.PAUSED

    def test_reset_works_on_any_phase(self):
        """Reset works on any phase."""
        timer = PomodoroTimer(short_mins=5)
        timer.next_phase()  # Move to short break
        assert timer.phase == Phase.SHORT_BREAK

        timer.start()
        for _ in range(50):
            timer.tick()

        timer.reset()
        assert timer.remaining_seconds == 5 * 60


class TestPhaseRotation:
    """Test phase rotation logic."""

    def test_work_to_short_break(self):
        """Work phase transitions to short break."""
        timer = PomodoroTimer(cycle_size=4)
        assert timer.phase == Phase.WORK
        assert timer.completed_in_cycle == 0

        timer.next_phase()
        assert timer.phase == Phase.SHORT_BREAK
        assert timer.completed_in_cycle == 1

    def test_short_break_to_work(self):
        """Short break transitions back to work."""
        timer = PomodoroTimer()
        timer.next_phase()  # Work -> Short break
        timer.next_phase()  # Short break -> Work
        assert timer.phase == Phase.WORK

    def test_long_break_after_cycle(self):
        """Long break occurs after cycle_size work phases."""
        timer = PomodoroTimer(cycle_size=4)

        # Complete 3 work + short break cycles
        for i in range(3):
            timer.next_phase()  # Work -> Short break
            timer.next_phase()  # Short break -> Work

        # 4th work phase should lead to long break
        assert timer.completed_in_cycle == 3
        timer.next_phase()  # 4th Work -> Long break
        assert timer.phase == Phase.LONG_BREAK
        assert timer.completed_in_cycle == 0  # Cycle resets

    def test_long_break_to_new_cycle(self):
        """Long break transitions to new work cycle."""
        timer = PomodoroTimer(cycle_size=2)

        # Complete a full cycle
        timer.next_phase()  # Work 1 -> Short break
        timer.next_phase()  # Short break -> Work 2
        timer.next_phase()  # Work 2 -> Long break
        assert timer.phase == Phase.LONG_BREAK

        timer.next_phase()  # Long break -> Work
        assert timer.phase == Phase.WORK
        assert timer.completed_in_cycle == 0

    def test_full_cycle_integration(self):
        """Full cycle runs correctly with tick countdown."""
        timer = PomodoroTimer(work_mins=1, short_mins=1, long_mins=1, cycle_size=2, auto_break=True, auto_work=True)
        timer.start()

        phases_seen = [Phase.WORK]

        # Run through a full cycle
        for _ in range(10000):  # Safety limit
            completed = timer.tick()
            if completed:
                phases_seen.append(timer.phase)
                if len(phases_seen) >= 6:
                    break

        # Work -> Short -> Work -> Long -> Work
        expected = [Phase.WORK, Phase.SHORT_BREAK, Phase.WORK, Phase.LONG_BREAK, Phase.WORK]
        assert phases_seen[:5] == expected


class TestAutoStartToggles:
    """Test auto-start behavior."""

    def test_auto_break_on(self):
        """Auto break starts break automatically."""
        timer = PomodoroTimer(auto_break=True, auto_work=False)
        timer.next_phase()
        assert timer.phase == Phase.SHORT_BREAK
        assert timer.status == Status.RUNNING

    def test_auto_break_off(self):
        """No auto break means break starts paused."""
        timer = PomodoroTimer(auto_break=False, auto_work=False)
        timer.next_phase()
        assert timer.phase == Phase.SHORT_BREAK
        assert timer.status == Status.PAUSED

    def test_auto_work_on(self):
        """Auto work starts work automatically after break."""
        timer = PomodoroTimer(auto_break=False, auto_work=True)
        timer.next_phase()  # Work -> Short break (paused)
        assert timer.status == Status.PAUSED

        timer.next_phase()  # Short break -> Work (running)
        assert timer.phase == Phase.WORK
        assert timer.status == Status.RUNNING

    def test_auto_work_off(self):
        """No auto work means work starts paused after break."""
        timer = PomodoroTimer(auto_break=False, auto_work=False)
        timer.next_phase()  # Work -> Short break
        timer.next_phase()  # Short break -> Work
        assert timer.phase == Phase.WORK
        assert timer.status == Status.PAUSED


class TestPrevPhase:
    """Test previous phase behavior."""

    def test_prev_from_short_break(self):
        """Previous from short break goes to work."""
        timer = PomodoroTimer()
        timer.next_phase()  # Work -> Short break
        assert timer.phase == Phase.SHORT_BREAK
        assert timer.completed_in_cycle == 1

        timer.prev_phase()
        assert timer.phase == Phase.WORK
        assert timer.completed_in_cycle == 0

    def test_prev_from_work_mid_cycle(self):
        """Previous from work mid-cycle goes to short break."""
        timer = PomodoroTimer(cycle_size=4)
        timer.next_phase()  # Work -> Short break
        timer.next_phase()  # Short break -> Work (2nd work)
        assert timer.completed_in_cycle == 1

        timer.prev_phase()
        assert timer.phase == Phase.SHORT_BREAK

    def test_prev_pauses_timer(self):
        """Previous always pauses the timer."""
        timer = PomodoroTimer(auto_break=True)
        timer.next_phase()
        assert timer.status == Status.RUNNING  # Auto-started

        timer.prev_phase()
        assert timer.status == Status.PAUSED


class TestProgress:
    """Test progress calculation."""

    def test_progress_at_start(self):
        """Progress is 0 at start of phase."""
        timer = PomodoroTimer(work_mins=1)
        assert timer.progress == 0.0

    def test_progress_at_halfway(self):
        """Progress is 0.5 at halfway point."""
        timer = PomodoroTimer(work_mins=1)
        timer._remaining = 30
        assert timer.progress == 0.5

    def test_progress_near_end(self):
        """Progress approaches 1.0 near end."""
        timer = PomodoroTimer(work_mins=1)
        timer._remaining = 1
        assert timer.progress > 0.98


class TestLabels:
    """Test display labels."""

    def test_phase_labels(self):
        """Phase labels are correct."""
        timer = PomodoroTimer(cycle_size=2)
        assert timer.phase_label == "Pomodoro"

        timer.next_phase()
        assert timer.phase_label == "Short Break"

        timer.next_phase()  # Work 2
        timer.next_phase()  # Long break
        assert timer.phase_label == "Long Break"

    def test_status_labels(self):
        """Status labels are correct."""
        timer = PomodoroTimer()
        assert timer.status_label == "PAUSED"

        timer.start()
        assert timer.status_label == "RUNNING"

    def test_cycle_display(self):
        """Cycle display is correct."""
        timer = PomodoroTimer(cycle_size=4)
        assert timer.cycle_display == "1/4"  # First work

        timer.next_phase()  # Short break
        assert timer.cycle_display == "1/4"  # Shows completed

        timer.next_phase()  # Work 2
        assert timer.cycle_display == "2/4"


class TestCallback:
    """Test phase complete callback."""

    def test_callback_called_on_next_phase(self):
        """Callback is called when next_phase is triggered."""
        callback_data = []

        def callback(old, new):
            callback_data.append((old, new))

        timer = PomodoroTimer(on_phase_complete=callback)
        timer.next_phase()

        assert len(callback_data) == 1
        assert callback_data[0] == (Phase.WORK, Phase.SHORT_BREAK)

    def test_callback_called_on_tick_completion(self):
        """Callback is called when tick completes a phase."""
        callback_data = []

        def callback(old, new):
            callback_data.append((old, new))

        timer = PomodoroTimer(work_mins=1, on_phase_complete=callback)
        timer._remaining = 1
        timer.start()
        timer.tick()

        assert len(callback_data) == 1
        assert callback_data[0] == (Phase.WORK, Phase.SHORT_BREAK)
