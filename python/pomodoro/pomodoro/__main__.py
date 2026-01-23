"""Entry point for python -m pomodoro."""

import argparse
import sys

from .scheduler import PomodoroTimer, Phase
from .notifications import notify
from .ui import run_ui


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Terminal Pomodoro timer styled like pomodoro.io",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Controls:
  Space    Start/Pause (primary action)
  r        Reset current phase
  n        Next phase (skip)
  p        Previous phase
  q        Quit

Examples:
  pomodoro                    # Default settings (25/5/15, auto-break on)
  pomodoro --work 50          # 50-minute pomodoros
  pomodoro --auto             # Auto-start both work and breaks
  pomodoro --no-auto-break    # Pause when work ends
""",
    )

    parser.add_argument(
        "--work",
        type=int,
        default=25,
        metavar="MINS",
        help="Work phase duration in minutes (default: 25)",
    )
    parser.add_argument(
        "--short",
        type=int,
        default=5,
        metavar="MINS",
        help="Short break duration in minutes (default: 5)",
    )
    parser.add_argument(
        "--long",
        type=int,
        default=15,
        metavar="MINS",
        help="Long break duration in minutes (default: 15)",
    )
    parser.add_argument(
        "--cycle",
        type=int,
        default=4,
        metavar="N",
        help="Work phases before long break (default: 4)",
    )

    # Auto behavior
    auto_group = parser.add_mutually_exclusive_group()
    auto_group.add_argument(
        "--auto",
        action="store_true",
        help="Auto-start both breaks and work phases",
    )

    parser.add_argument(
        "--auto-break",
        action="store_true",
        default=True,
        dest="auto_break",
        help="Auto-start breaks when work ends (default: on)",
    )
    parser.add_argument(
        "--no-auto-break",
        action="store_false",
        dest="auto_break",
        help="Don't auto-start breaks",
    )

    parser.add_argument(
        "--auto-work",
        action="store_true",
        default=False,
        dest="auto_work",
        help="Auto-start work when break ends (default: off)",
    )
    parser.add_argument(
        "--no-auto-work",
        action="store_false",
        dest="auto_work",
        help="Don't auto-start work phases",
    )

    # Notifications
    parser.add_argument(
        "--no-notify",
        action="store_true",
        help="Disable notifications (bell and system)",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Handle --auto flag
    auto_break = args.auto_break
    auto_work = args.auto_work
    if args.auto:
        auto_break = True
        auto_work = True

    notify_enabled = not args.no_notify

    def on_phase_complete(old_phase: Phase, new_phase: Phase) -> None:
        """Notification callback."""
        if not notify_enabled:
            return

        if old_phase == Phase.WORK:
            title = "Pomodoro Complete!"
            if new_phase == Phase.LONG_BREAK:
                message = "Time for a long break. You've earned it!"
            else:
                message = "Time for a short break."
        else:
            title = "Break Over"
            message = "Ready to focus?"

        notify(title, message, bell=True)

    timer = PomodoroTimer(
        work_mins=args.work,
        short_mins=args.short,
        long_mins=args.long,
        cycle_size=args.cycle,
        auto_break=auto_break,
        auto_work=auto_work,
    )

    try:
        run_ui(timer, notify_enabled, on_phase_complete=on_phase_complete)
    except KeyboardInterrupt:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
