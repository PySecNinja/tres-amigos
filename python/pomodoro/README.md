# Terminal Pomodoro Timer

A terminal Pomodoro timer styled like [pomodoro.io](https://pomodoro.io) - big, clean countdown; simple controls; clear phase switching; minimal distractions.

## Screenshot

```
            ── Pomodoro 1/4 ──

             ██    ███    ██    ██
            █  █  █      █  █  █  █
               █   ██    █  █  █  █
              █       █  █  █  █  █
            ████  ███     ██    ██

                  RUNNING

            ████████████░░░░░░░░░░░░

   Space:Start/Pause  r:Reset  n:Next  p:Prev  q:Quit
```

## Installation

```bash
# Just run it - venv is created automatically
./pomo

# First run will offer to create a symlink so you can run 'pomo' from anywhere
# Or run setup manually:
./pomo --setup
```

## Usage

```bash
# Run with default settings (25/5/15 minutes, auto-break on)
pomo

# Custom work duration (50-minute pomodoros)
pomo --work 50

# Custom break durations
pomo --short 10 --long 30

# Auto-start everything (no pauses between phases)
pomo --auto

# Disable auto-break (pause when work ends)
pomo --no-auto-break

# Disable notifications
pomo --no-notify
```

## Controls

| Key   | Action                    |
|-------|---------------------------|
| Space | Start/Pause (primary)     |
| r     | Reset current phase       |
| n     | Next phase (skip)         |
| p     | Previous phase            |
| q     | Quit                      |

## Phases

The timer cycles through:

1. **Pomodoro** (25 min default) - Focus work time
2. **Short Break** (5 min default) - Quick rest
3. After 4 pomodoros: **Long Break** (15 min default)

The cycle counter shows your progress: `Pomodoro 2/4` means you're on your 2nd work session before the long break.

## Options

| Option            | Default | Description                           |
|-------------------|---------|---------------------------------------|
| `--work MINS`     | 25      | Work phase duration                   |
| `--short MINS`    | 5       | Short break duration                  |
| `--long MINS`     | 15      | Long break duration                   |
| `--cycle N`       | 4       | Work phases before long break         |
| `--auto-break`    | on      | Auto-start breaks when work ends      |
| `--no-auto-break` | -       | Don't auto-start breaks               |
| `--auto-work`     | off     | Auto-start work when break ends       |
| `--auto`          | -       | Enable both auto-break and auto-work  |
| `--no-notify`     | -       | Disable notifications                 |

## Notifications

When a phase completes:
- Terminal bell sounds (unless `--no-notify`)
- macOS: Native notification via osascript
- Linux: Notification via notify-send (if available)

## Running Tests

```bash
./venv/bin/python -m pytest tests/ -v
```

## Project Structure

```
pomodoro/
├── pomo                  # Bash entry point (handles venv automatically)
├── pomodoro/
│   ├── __init__.py       # Package init
│   ├── __main__.py       # CLI entry point
│   ├── scheduler.py      # Timer state machine (pure logic)
│   ├── ui.py             # Curses-based terminal UI
│   └── notifications.py  # Bell + native notifications
├── tests/
│   └── test_scheduler.py # Unit tests
├── requirements.txt      # Dependencies
└── README.md
```
