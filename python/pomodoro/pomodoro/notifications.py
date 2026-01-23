"""Notification support for Pomodoro timer."""

import subprocess
import sys
import platform


def _send_bell() -> None:
    """Send terminal bell."""
    sys.stdout.write("\a")
    sys.stdout.flush()


def _send_macos_notification(title: str, message: str) -> bool:
    """Send macOS notification via osascript.

    Returns:
        True if successful, False otherwise.
    """
    script = f'display notification "{message}" with title "{title}"'
    try:
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=5,
        )
        return True
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return False


def _send_linux_notification(title: str, message: str) -> bool:
    """Send Linux notification via notify-send.

    Returns:
        True if successful, False otherwise.
    """
    try:
        subprocess.run(
            ["notify-send", title, message],
            capture_output=True,
            timeout=5,
        )
        return True
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return False


def notify(title: str, message: str, bell: bool = True) -> None:
    """Send a notification.

    Attempts to send both a terminal bell and a native notification.
    Fails silently if native notifications are not available.

    Args:
        title: Notification title.
        message: Notification message.
        bell: Whether to ring terminal bell.
    """
    if bell:
        _send_bell()

    system = platform.system()
    if system == "Darwin":
        _send_macos_notification(title, message)
    elif system == "Linux":
        _send_linux_notification(title, message)
    # Windows and other platforms: bell only
