# Jobflare

Small utility to open a list of job URLs in Google Chrome.

## Setup

Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install rich httpx
```

After activating the venv, `jobflare` is available as a command.

## Run

```bash
. .venv/bin/activate
jobflare profiles/jobs_test.txt
```

Dry run (no tabs opened):

```bash
. .venv/bin/activate
jobflare --dry-run profiles/jobs_test.txt
```

Validate/update a file (checks URLs in the background; you can return to the main menu):

```bash
. .venv/bin/activate
jobflare
```

## Fetch Fresh Links

Use the fetcher to grab fresh links from supported providers and write them to a file.

```bash
. .venv/bin/activate
python3 fetch_jobs.py search_specs.json
jobflare jobs_fetched.txt
```

### Config

Edit `search_specs.json` to control providers and filters.

- `greenhouse` and `lever` call their public APIs.
- `google_jobs` generates a Google Jobs search URL.
- Company IDs are the public board slugs (often visible in the jobs URL).

## Notes

- `profiles/jobs_test.txt` is a small sample list to avoid opening too many tabs.
- The script ignores blank lines and lines starting with `#`.
- The menu supports batch opening with optional pauses.
- Invalid lines are skipped (whitespace, missing host, or non-http/https).
- A cleaned list is always written as `*_clean.txt`.
- Put profile files in `profiles/` and select by profile (filename stem).
- Menus accept `b` to go back; validation has its own control menu.
- Default tab limit is 10 unless you change it in the prompt.
