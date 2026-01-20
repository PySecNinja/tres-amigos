# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python3 -m venv .venv
. .venv/bin/activate
pip install rich httpx

# Run the TUI
python3 jobflare.py

# Run with a specific profile file
python3 jobflare.py profiles/test/jobs.txt

# Dry run (no tabs opened)
python3 jobflare.py --dry-run profiles/test/jobs.txt

# Fetch fresh job links for a profile
python3 fetch_jobs.py profiles/cyber/search_specs.json profiles/cyber
```

## Architecture

**jobflare.py** - Main TUI application using `rich` for terminal UI and `httpx` for HTTP validation.
- State machine with `Screen` enum: MAIN_MENU, PROFILE_SELECT, OPEN_SETTINGS, OPENING, VALIDATING, FETCHING, QUIT
- `AppState` dataclass tracks current screen, profile, selection index, validation progress
- Vim-style navigation: j/k to navigate, Enter to select, b to go back, q to quit
- Opens job URLs in Google Chrome via AppleScript (`osascript`)
- Background URL validation with threading
- Writes validated lists to `jobs_validated.txt` and reports to `jobs_report.txt` in profile directory

**fetch_jobs.py** - Job listing fetcher supporting multiple providers:
- `greenhouse`: Fetches from Greenhouse Boards API
- `lever`: Fetches from Lever Postings API
- `google_jobs`: Generates Google Jobs search URLs
- Accepts config path and optional output directory as arguments

**profiles/** - Directory-based profile structure:
```
profiles/
  cyber/
    jobs.txt              # URL list
    search_specs.json     # Optional fetch config
  test/
    jobs.txt
```

## Key Patterns

- `Profile.from_directory()` loads profile from directory with jobs.txt and optional search_specs.json
- `read_key()` handles raw terminal input for vim-style single-key navigation
- URL normalization: `normalize_url()` handles scheme defaults and validation
- All HTTP requests use `httpx.Client` with custom User-Agent headers
- Validation runs in a background thread with cancel support via `threading.Event`
