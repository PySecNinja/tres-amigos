# Project Instructions

## Purpose
JOBFLAIR is a Python TUI that opens job URLs in Chrome, validates links, and manages profile-based lists.

## Key Files
- `jobflare.py`: Main TUI app and logic.
- `fetch_jobs.py`: Optional fetcher for fresh links (network required).
- `profiles/`: Directory containing profile `.txt` files (e.g., `profiles/cyber.txt`).
- `profiles/jobs_test.txt`: Small test list.
- `search_specs.json`: Config for `fetch_jobs.py`.
- `README.md`: Usage notes.

## Environment
- Virtual env at `.venv`.
- Activate: `. .venv/bin/activate`
- After activation, `jobflare` command is available via `.venv/bin/jobflare`.

## Common Commands
- Run TUI: `jobflare`
- Dry run: `jobflare --dry-run profiles/jobs_test.txt`
- Validate/update links (background): `jobflare` → menu option 3
- Fetch fresh links: `python3 fetch_jobs.py search_specs.json`

## Behavior Notes
- Default max tabs is 10 (prompt can override).
- Cleaned URLs are always written to `*_clean.txt`.
- Validation writes `*_validated.txt` and `*_report.txt`.
- Menus accept `b` to go back; validation submenu uses `b`/`r`/`c`.

## Profiles
- Place job lists in `profiles/` to appear in the profile selector.
- Profile names are derived from filename stem.

## Dependencies
- `rich` for TUI
- `httpx` for validation and fetching (network needed when validating or fetching)

## Network Access
Validation and fetcher perform HTTP requests when run. Ensure network access is allowed.
