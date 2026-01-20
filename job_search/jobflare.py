#!/usr/bin/env python3
"""Jobflare - A refined TUI for managing job search URLs."""

import json
import subprocess
import sys
import termios
import threading
import time
import tty
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_TAB_LIMIT = 10
DEFAULT_DELAY = 0.15
DEFAULT_TIMEOUT = 8.0

BANNER = """
       ██  ██████  ██████  ███████ ██       █████  ██████  ███████
       ██ ██    ██ ██   ██ ██      ██      ██   ██ ██   ██ ██
       ██ ██    ██ ██████  █████   ██      ███████ ██████  █████
  ██   ██ ██    ██ ██   ██ ██      ██      ██   ██ ██   ██ ██
   █████   ██████  ██████  ██      ███████ ██   ██ ██   ██ ███████
"""


# ─────────────────────────────────────────────────────────────────────────────
# State Machine
# ─────────────────────────────────────────────────────────────────────────────


class Screen(Enum):
    MAIN_MENU = auto()
    PROFILE_SELECT = auto()
    OPEN_SETTINGS = auto()
    OPENING = auto()
    VALIDATING = auto()
    FETCHING = auto()
    AI_PROMPT_KEYWORDS = auto()
    AI_PROMPT_LOCATIONS = auto()
    AI_PROMPT_COMPANIES = auto()
    AI_PROMPT_DISPLAY = auto()
    QUIT = auto()


# Default company list for cyber security job searches
DEFAULT_COMPANIES = [
    "Anduril", "Palantir", "CrowdStrike", "Palo Alto Networks", "Fortinet",
    "Splunk", "Elastic", "Cloudflare", "Zscaler", "SentinelOne",
    "Lockheed Martin", "Northrop Grumman", "Raytheon (RTX)", "Boeing", "BAE Systems",
    "L3Harris", "General Dynamics", "Leidos", "SAIC", "Booz Allen",
    "MITRE", "Peraton", "ManTech", "Parsons", "CACI",
    "Microsoft", "Google", "Amazon (AWS)", "Apple", "Meta",
    "Netflix", "Cisco", "IBM", "Oracle", "VMware",
    "BlueHalo", "Bluestaq", "True Anomaly", "Sierra Space", "Auria Space",
    "Delta Sands", "Pryon", "Trellix", "Mandiant", "Recorded Future",
]


@dataclass
class Profile:
    name: str
    path: Path
    jobs_file: Path
    search_specs: Optional[Path] = None
    urls: List[str] = field(default_factory=list)
    url_count: int = 0

    @classmethod
    def from_directory(cls, path: Path) -> Optional["Profile"]:
        jobs_file = path / "jobs.txt"
        if not jobs_file.exists():
            return None
        search_specs = path / "search_specs.json"
        if not search_specs.exists():
            search_specs = None
        profile = cls(
            name=path.name,
            path=path,
            jobs_file=jobs_file,
            search_specs=search_specs,
        )
        profile.reload_urls()
        return profile

    def reload_urls(self) -> None:
        self.urls, _, _ = read_urls(self.jobs_file)
        self.url_count = len(self.urls)


@dataclass
class AppState:
    screen: Screen = Screen.MAIN_MENU
    prev_screen: Screen = Screen.MAIN_MENU
    profiles: List[Profile] = field(default_factory=list)
    profile_idx: int = 0
    selection_idx: int = 0
    message: str = ""
    # Open settings
    tab_limit: int = DEFAULT_TAB_LIMIT
    delay: float = DEFAULT_DELAY
    # Validation state
    validation_thread: Optional[threading.Thread] = None
    validation_cancel: threading.Event = field(default_factory=threading.Event)
    validation_status: str = "idle"
    validation_total: int = 0
    validation_completed: int = 0
    validation_valid: int = 0
    validation_failed: int = 0
    validation_error: str = ""
    # AI prompt builder
    ai_prompt: str = ""
    ai_keywords: List[str] = field(default_factory=list)
    ai_locations: List[str] = field(default_factory=list)
    ai_companies: List[str] = field(default_factory=list)
    ai_company_selected: Dict[str, bool] = field(default_factory=dict)
    ai_company_filter: str = ""
    ai_filtered_companies: List[str] = field(default_factory=list)

    @property
    def current_profile(self) -> Optional[Profile]:
        if not self.profiles:
            return None
        return self.profiles[self.profile_idx]

    def load_profiles(self, profiles_dir: Path) -> None:
        self.profiles = []
        if not profiles_dir.exists():
            return
        for d in sorted(profiles_dir.iterdir()):
            if d.is_dir():
                profile = Profile.from_directory(d)
                if profile:
                    self.profiles.append(profile)


# ─────────────────────────────────────────────────────────────────────────────
# Input Handling
# ─────────────────────────────────────────────────────────────────────────────


def read_key() -> str:
    """Read a single keypress, handling arrow keys."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":  # Escape sequence
            ch2 = sys.stdin.read(1)
            if ch2 == "[":
                ch3 = sys.stdin.read(1)
                if ch3 == "A":
                    return "up"
                elif ch3 == "B":
                    return "down"
                elif ch3 == "C":
                    return "right"
                elif ch3 == "D":
                    return "left"
            return "esc"
        elif ch == "\r" or ch == "\n":
            return "enter"
        elif ch == "\x03":  # Ctrl+C
            return "q"
        return ch.lower()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def read_number(prompt: str, default: int, max_val: int) -> int:
    """Read a number from user input."""
    console.print(f"  {prompt} [dim](default {default})[/dim]: ", end="")
    buffer = ""
    while True:
        ch = read_key()
        if ch == "enter":
            console.print()
            if not buffer:
                return default
            try:
                val = int(buffer)
                return min(max(1, val), max_val)
            except ValueError:
                return default
        elif ch == "b" or ch == "esc":
            console.print()
            return -1
        elif ch.isdigit():
            buffer += ch
            console.print(ch, end="")
        elif ch == "\x7f":  # Backspace
            if buffer:
                buffer = buffer[:-1]
                console.print("\b \b", end="")


def read_text_input(prompt: str, existing: str = "") -> Tuple[str, bool]:
    """Read text input. Returns (text, cancelled)."""
    console.print(f"  {prompt}: ", end="")
    buffer = existing
    if buffer:
        console.print(buffer, end="")
    while True:
        ch = read_key()
        if ch == "enter":
            console.print()
            return buffer.strip(), False
        elif ch == "esc":
            console.print()
            return "", True
        elif ch == "\x7f":  # Backspace
            if buffer:
                buffer = buffer[:-1]
                console.print("\b \b", end="")
        elif len(ch) == 1 and ch.isprintable():
            buffer += ch
            console.print(ch, end="")


# ─────────────────────────────────────────────────────────────────────────────
# URL Handling
# ─────────────────────────────────────────────────────────────────────────────


def normalize_url(raw: str) -> Optional[str]:
    line = raw.strip().replace("\r", "")
    if not line or line.startswith("#"):
        return None
    if any(ch.isspace() for ch in line):
        return None
    parsed = urlparse(line)
    if not parsed.scheme:
        line = f"https://{line}"
        parsed = urlparse(line)
    if parsed.scheme not in ("http", "https"):
        return None
    if not parsed.netloc:
        return None
    return line


def read_urls(jobs_file: Path) -> Tuple[List[str], int, int]:
    if not jobs_file.exists():
        return [], 0, 0
    urls = []
    skipped = 0
    total = 0
    for raw in jobs_file.read_text(encoding="utf-8", errors="replace").splitlines():
        total += 1
        url = normalize_url(raw)
        if url is None:
            if raw.strip():
                skipped += 1
            continue
        urls.append(url)
    return urls, skipped, total


def escape_applescript_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def open_in_chrome(url: str) -> None:
    safe_url = escape_applescript_string(url)
    script = f'tell application "Google Chrome" to open location "{safe_url}"'
    subprocess.run(["osascript", "-e", script], check=True)


# ─────────────────────────────────────────────────────────────────────────────
# Rendering
# ─────────────────────────────────────────────────────────────────────────────


def clear_screen() -> None:
    console.clear()


def render_banner() -> None:
    console.print("[bold cyan]" + BANNER + "[/bold cyan]")
    console.print("─" * 70, style="dim")


def render_footer(hints: str) -> None:
    console.print()
    console.print(f"  [dim]{hints}[/dim]")


def render_message(state: AppState) -> None:
    if state.message:
        console.print(f"\n  [yellow]{state.message}[/yellow]")
        state.message = ""


def render_shortcuts_panel() -> Panel:
    """Render browser shortcuts reference panel."""
    table = Table(box=None, show_header=False, padding=(0, 2))
    table.add_column("Action", style="dim")
    table.add_column("Key", style="cyan")
    table.add_row("Focus address bar", "Cmd+L")
    table.add_row("Close tab", "Cmd+W")
    table.add_row("Reopen closed tab", "Cmd+Shift+T")
    table.add_row("Next tab", "Cmd+Option+Right")
    table.add_row("Prev tab", "Cmd+Option+Left")
    return Panel(table, title="[bold]Browser Shortcuts[/bold]", box=box.ROUNDED, border_style="dim")


def render_main_menu(state: AppState) -> None:
    clear_screen()
    render_banner()

    profile = state.current_profile
    if profile:
        console.print(f"  Profile: [bold cyan]{profile.name}[/bold cyan] [dim]({profile.url_count} jobs)[/dim]")
    else:
        console.print("  [yellow]No profiles found[/yellow]")

    console.print()

    # Actions menu as a clean list
    menu = Table(box=None, show_header=False, padding=(0, 1))
    menu.add_column("Key", style="bold cyan", width=4, justify="right")
    menu.add_column("Action")
    menu.add_row("o", "Open jobs in Chrome")
    menu.add_row("f", "Fetch from APIs (Greenhouse/Lever)")
    menu.add_row("g", "Generate AI prompt for new jobs")
    menu.add_row("v", "Validate links")
    menu.add_row("p", "Switch profile")
    menu.add_row("q", "Quit")
    console.print(Panel(menu, title="[bold]Actions[/bold]", box=box.ROUNDED, border_style="cyan"))

    # Browser shortcuts
    console.print(render_shortcuts_panel())

    render_message(state)
    render_footer("Press a key to select an action")


def render_profile_select(state: AppState) -> None:
    clear_screen()
    render_banner()
    console.print()

    # Profile list
    table = Table(box=None, show_header=False, padding=(0, 1))
    table.add_column("", width=2)
    table.add_column("Profile")
    table.add_column("Jobs", style="dim", justify="right")

    for i, profile in enumerate(state.profiles):
        if i == state.selection_idx:
            table.add_row("[cyan]>[/cyan]", f"[bold cyan]{profile.name}[/bold cyan]", str(profile.url_count))
        else:
            table.add_row("", profile.name, str(profile.url_count))

    console.print(Panel(table, title="[bold]Select Profile[/bold]", box=box.ROUNDED, border_style="cyan"))

    render_message(state)
    render_footer("j/k or arrows to navigate | Enter to select | b to go back")


def render_open_settings(state: AppState) -> None:
    clear_screen()
    render_banner()

    profile = state.current_profile
    if profile:
        console.print(f"  Profile: [bold cyan]{profile.name}[/bold cyan] [dim]({profile.url_count} jobs)[/dim]")
    console.print()
    console.print("  [bold]Configure Tab Opening[/bold]")
    console.print("  [dim]Press Enter for defaults, or b to cancel[/dim]")
    console.print()


def render_progress(label: str, completed: int, total: int, extra: str = "") -> None:
    if total == 0:
        pct = 0
    else:
        pct = int((completed / total) * 100)
    bar_width = 30
    filled = int(bar_width * completed / total) if total > 0 else 0
    bar = "[cyan]" + "█" * filled + "[/cyan]" + "[dim]░[/dim]" * (bar_width - filled)
    console.print(f"  {label}")
    console.print()
    console.print(f"  [{bar}]  {pct}%  {completed}/{total}")
    if extra:
        console.print()
        console.print(f"  {extra}")


def render_validating(state: AppState) -> None:
    clear_screen()
    render_banner()
    console.print()

    if state.validation_status == "running":
        extra = f"Valid: [green]{state.validation_valid}[/green]   Failed: [red]{state.validation_failed}[/red]"
        render_progress("Validating links...", state.validation_completed, state.validation_total, extra)
        console.print()
        console.print()
        console.print("  [cyan]c[/cyan]  Cancel validation")
        render_footer("Press c to cancel")
    elif state.validation_status == "done":
        table = Table(box=None, show_header=False, padding=(0, 2))
        table.add_column("Label")
        table.add_column("Count", justify="right")
        table.add_row("[green]Valid[/green]", f"[green]{state.validation_valid}[/green]")
        table.add_row("[red]Failed[/red]", f"[red]{state.validation_failed}[/red]")
        console.print(Panel(table, title="[bold green]Validation Complete[/bold green]", box=box.ROUNDED, border_style="green"))
        console.print()
        console.print("  [cyan]b[/cyan]  Back to menu")
        render_footer("Press b or Enter to go back")
    elif state.validation_status == "cancelled":
        console.print(Panel(
            f"Completed: {state.validation_completed}/{state.validation_total}\n"
            f"Valid: [green]{state.validation_valid}[/green]  Failed: [red]{state.validation_failed}[/red]",
            title="[bold yellow]Validation Cancelled[/bold yellow]",
            box=box.ROUNDED,
            border_style="yellow"
        ))
        console.print()
        console.print("  [cyan]b[/cyan]  Back to menu")
        render_footer("Press b or Enter to go back")
    elif state.validation_status == "error":
        console.print(Panel(
            f"Error: {state.validation_error}",
            title="[bold red]Validation Failed[/bold red]",
            box=box.ROUNDED,
            border_style="red"
        ))
        console.print()
        console.print("  [cyan]b[/cyan]  Back to menu")
        render_footer("Press b or Enter to go back")


def render_fetching(state: AppState) -> None:
    clear_screen()
    render_banner()
    console.print()
    profile = state.current_profile
    console.print(Panel(
        f"Fetching from: [cyan]{profile.search_specs.name}[/cyan]\n"
        f"Please wait...",
        title="[bold]Fetching Jobs[/bold]",
        box=box.ROUNDED,
        border_style="cyan"
    ))
    console.print()


# ─────────────────────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────────────────────


def run_validation(state: AppState, profile: Profile) -> None:
    """Run validation in background thread."""
    urls = profile.urls
    validated = []
    failed = []
    try:
        with httpx.Client(
            follow_redirects=True, headers={"User-Agent": "jobflare/1.0"}
        ) as client:
            for url in urls:
                if state.validation_cancel.is_set():
                    state.validation_status = "cancelled"
                    return
                ok_url = None
                try:
                    resp = client.head(url, timeout=DEFAULT_TIMEOUT)
                    if resp.status_code >= 400:
                        resp = client.get(url, timeout=DEFAULT_TIMEOUT)
                    if resp.status_code < 400:
                        ok_url = str(resp.url)
                except httpx.HTTPError:
                    ok_url = None
                if ok_url:
                    validated.append(ok_url)
                else:
                    failed.append(url)
                state.validation_completed += 1
                state.validation_valid = len(validated)
                state.validation_failed = len(failed)

        # Write results
        validated_path = profile.jobs_file.with_name("jobs_validated.txt")
        report_path = profile.jobs_file.with_name("jobs_report.txt")
        validated_path.write_text("\n".join(validated) + "\n", encoding="utf-8")
        report_lines = [
            f"Validated: {len(validated)}",
            f"Failed: {len(failed)}",
            "",
            "Failed URLs:",
            *failed,
        ]
        report_path.write_text("\n".join(report_lines).strip() + "\n", encoding="utf-8")
        state.validation_status = "done"
    except Exception as exc:
        state.validation_status = "error"
        state.validation_error = str(exc)


def start_validation(state: AppState) -> None:
    profile = state.current_profile
    if not profile or not profile.urls:
        state.message = "No URLs to validate"
        return
    state.validation_cancel.clear()
    state.validation_status = "running"
    state.validation_total = len(profile.urls)
    state.validation_completed = 0
    state.validation_valid = 0
    state.validation_failed = 0
    state.validation_error = ""
    state.validation_thread = threading.Thread(
        target=run_validation, args=(state, profile), daemon=True
    )
    state.validation_thread.start()


# ─────────────────────────────────────────────────────────────────────────────
# Fetch Jobs
# ─────────────────────────────────────────────────────────────────────────────


def fetch_jobs_for_profile(profile: Profile) -> Tuple[int, str]:
    """Run fetch_jobs.py for a profile with search_specs.json."""
    if not profile.search_specs:
        return 0, "No search_specs.json in profile"
    try:
        result = subprocess.run(
            [sys.executable, "fetch_jobs.py", str(profile.search_specs), str(profile.path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            return 0, result.stderr.strip() or "Fetch failed"
        # Count new URLs
        output = result.stdout.strip()
        for line in output.splitlines():
            if "Wrote" in line and "URLs" in line:
                try:
                    count = int(line.split()[1])
                    return count, ""
                except (IndexError, ValueError):
                    pass
        return 0, output
    except subprocess.TimeoutExpired:
        return 0, "Fetch timed out"
    except Exception as e:
        return 0, str(e)


# ─────────────────────────────────────────────────────────────────────────────
# AI Prompt Generation
# ─────────────────────────────────────────────────────────────────────────────


def load_search_specs(profile: Profile) -> Optional[Dict[str, Any]]:
    """Load search_specs.json for a profile if it exists."""
    if not profile.search_specs or not profile.search_specs.exists():
        return None
    try:
        return json.loads(profile.search_specs.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return None


def generate_ai_prompt_from_specs(profile: Profile) -> str:
    """Generate an AI prompt from profile's search_specs.json."""
    specs = load_search_specs(profile)

    keywords = []
    locations = []
    companies = []

    if specs and "sources" in specs:
        for source in specs["sources"]:
            if "keywords" in source:
                keywords.extend(source["keywords"])
            if "locations" in source:
                locations.extend(source["locations"])
            if "company" in source:
                companies.append(source["company"])

    # Deduplicate
    keywords = list(dict.fromkeys(keywords))
    locations = list(dict.fromkeys(locations))
    companies = list(dict.fromkeys(companies))

    return generate_ai_prompt(keywords, locations, companies)


def generate_ai_prompt(keywords: List[str], locations: List[str], companies: List[str]) -> str:
    """Generate an AI prompt for finding job URLs."""

    # Build the prompt
    prompt_parts = [
        "# Job URL Search Request",
        "",
        "Find job posting URLs matching my criteria. Return ONLY valid, working URLs to active job listings.",
        "",
        "## Search Criteria",
        "",
    ]

    if keywords:
        prompt_parts.append(f"**Keywords:** {', '.join(keywords)}")
    if locations:
        prompt_parts.append(f"**Locations:** {', '.join(locations)}")
    if companies:
        prompt_parts.append(f"**Target Companies:** {', '.join(companies)}")

    prompt_parts.extend([
        "",
        "## Instructions",
        "",
        "1. Search for job postings matching the criteria above",
        "2. Find direct links to individual job postings (not search results pages)",
        "3. Prioritize jobs from company career pages, Greenhouse, Lever, Workday, and iCIMS",
        "4. Verify each URL points to an active job posting",
        "",
        "## Output Format",
        "",
        "Return URLs with work-type tags. Use this EXACT format:",
        "",
        "```",
        "[REMOTE] https://example.com/jobs/12345",
        "[HYBRID] https://company.greenhouse.io/jobs/67890",
        "[ON-SITE: Denver, CO] https://jobs.lever.co/company/abcdef",
        "[REMOTE] https://careers.company.com/jobs/99999",
        "```",
        "",
        "## Tag Definitions",
        "",
        "- `[REMOTE]` - Fully remote position",
        "- `[HYBRID]` - Mix of remote and on-site",
        "- `[ON-SITE: Location]` - Must work at specific location",
        "- If work type is unclear, use `[UNKNOWN]`",
        "",
        "## Requirements",
        "",
        "- Return 20-50 unique job URLs",
        "- Each URL must be a direct link to a specific job posting",
        "- URLs must start with https:// or http://",
        "- No duplicate URLs",
        "- No expired or closed job postings",
        "- No general career page URLs (must be specific job listings)",
        "",
        "## Example Valid URLs",
        "",
        "- `https://boards.greenhouse.io/company/jobs/123456`",
        "- `https://jobs.lever.co/company/abc-def-123`",
        "- `https://company.wd5.myworkdayjobs.com/careers/job/Location/Title_ID`",
        "- `https://careers.company.com/jobs/12345`",
        "",
        "Provide the tagged job URLs now, one per line.",
    ])

    return "\n".join(prompt_parts)


def copy_to_clipboard(text: str) -> bool:
    """Copy text to clipboard using pbcopy (macOS)."""
    try:
        subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


COMPANY_BATCH_SIZE = 10


def init_ai_prompt_builder(state: AppState) -> None:
    """Initialize the AI prompt builder with defaults."""
    # Load from search_specs if available
    specs = load_search_specs(state.current_profile) if state.current_profile else None

    state.ai_keywords = []
    state.ai_locations = []
    state.ai_companies = DEFAULT_COMPANIES.copy()
    state.ai_company_selected = [False] * len(DEFAULT_COMPANIES)
    state.ai_company_batch_idx = 0
    state.ai_input_buffer = ""

    # Pre-populate from search_specs
    if specs and "sources" in specs:
        for source in specs["sources"]:
            if "keywords" in source:
                for kw in source["keywords"]:
                    if kw not in state.ai_keywords:
                        state.ai_keywords.append(kw)
            if "locations" in source:
                for loc in source["locations"]:
                    if loc not in state.ai_locations:
                        state.ai_locations.append(loc)


def render_ai_keywords(state: AppState) -> None:
    """Render the keywords input screen."""
    clear_screen()
    render_banner()
    console.print()
    console.print("  [bold]Step 1/3: Keywords[/bold]")
    console.print("  [dim]Enter job-related keywords (e.g., cyber, security, engineer)[/dim]")
    console.print()

    if state.ai_keywords:
        console.print(f"  Current: [cyan]{', '.join(state.ai_keywords)}[/cyan]")
    else:
        console.print("  Current: [dim]none[/dim]")

    console.print()
    console.print("  [cyan]a[/cyan]  Add keyword")
    console.print("  [cyan]c[/cyan]  Clear all")
    console.print("  [cyan]n[/cyan]  Next step (locations)")
    console.print("  [cyan]b[/cyan]  Back to menu")
    render_footer("Press a key to select")


def handle_ai_keywords(state: AppState, key: str) -> None:
    """Handle keywords screen input."""
    if key == "a":
        console.print()
        text, cancelled = read_text_input("Enter keyword")
        if not cancelled and text:
            # Support comma-separated keywords
            for kw in text.split(","):
                kw = kw.strip()
                if kw and kw not in state.ai_keywords:
                    state.ai_keywords.append(kw)
    elif key == "c":
        state.ai_keywords = []
    elif key == "n":
        state.screen = Screen.AI_PROMPT_LOCATIONS
    elif key in ("b", "esc"):
        state.screen = Screen.MAIN_MENU


def render_ai_locations(state: AppState) -> None:
    """Render the locations input screen."""
    clear_screen()
    render_banner()
    console.print()
    console.print("  [bold]Step 2/3: Locations[/bold]")
    console.print("  [dim]Enter preferred locations (e.g., remote, Colorado, Denver)[/dim]")
    console.print()

    if state.ai_locations:
        console.print(f"  Current: [cyan]{', '.join(state.ai_locations)}[/cyan]")
    else:
        console.print("  Current: [dim]none[/dim]")

    console.print()
    console.print("  [cyan]a[/cyan]  Add location")
    console.print("  [cyan]c[/cyan]  Clear all")
    console.print("  [cyan]n[/cyan]  Next step (companies)")
    console.print("  [cyan]b[/cyan]  Back to keywords")
    render_footer("Press a key to select")


def handle_ai_locations(state: AppState, key: str) -> None:
    """Handle locations screen input."""
    if key == "a":
        console.print()
        text, cancelled = read_text_input("Enter location")
        if not cancelled and text:
            for loc in text.split(","):
                loc = loc.strip()
                if loc and loc not in state.ai_locations:
                    state.ai_locations.append(loc)
    elif key == "c":
        state.ai_locations = []
    elif key == "n":
        state.screen = Screen.AI_PROMPT_COMPANIES
    elif key in ("b", "esc"):
        state.screen = Screen.AI_PROMPT_KEYWORDS


def render_ai_companies(state: AppState) -> None:
    """Render the company selection screen with batching."""
    clear_screen()
    render_banner()
    console.print()
    console.print("  [bold]Step 3/3: Select Companies[/bold]")
    console.print()

    # Calculate batch info
    total = len(state.ai_companies)
    start = state.ai_company_batch_idx * COMPANY_BATCH_SIZE
    end = min(start + COMPANY_BATCH_SIZE, total)
    batch_num = state.ai_company_batch_idx + 1
    total_batches = (total + COMPANY_BATCH_SIZE - 1) // COMPANY_BATCH_SIZE

    selected_count = sum(state.ai_company_selected)
    console.print(f"  Selected: [cyan]{selected_count}[/cyan] companies  |  Batch {batch_num}/{total_batches}")
    console.print()

    # Show current batch
    table = Table(box=None, show_header=False, padding=(0, 1))
    table.add_column("Sel", width=3)
    table.add_column("#", width=3, style="dim")
    table.add_column("Company")

    for i in range(start, end):
        marker = "[green]X[/green]" if state.ai_company_selected[i] else " "
        num = str(i - start + 1)
        company = state.ai_companies[i]
        if i == state.selection_idx:
            table.add_row(marker, num, f"[bold cyan]{company}[/bold cyan]")
        else:
            table.add_row(marker, num, company)

    console.print(Panel(table, box=box.ROUNDED, border_style="cyan"))
    console.print()
    console.print("  [cyan]1-0[/cyan] Toggle company (0=10)  [cyan]space[/cyan] Toggle highlighted")
    console.print("  [cyan]j/k[/cyan] Navigate                [cyan]</>[/cyan] Prev/Next batch")
    console.print("  [cyan]a[/cyan]   Select all             [cyan]c[/cyan]   Clear all")
    console.print("  [cyan]n[/cyan]   Generate prompt        [cyan]b[/cyan]   Back to locations")
    render_footer("Select companies to include in search")


def handle_ai_companies(state: AppState, key: str) -> None:
    """Handle company selection input."""
    total = len(state.ai_companies)
    start = state.ai_company_batch_idx * COMPANY_BATCH_SIZE
    end = min(start + COMPANY_BATCH_SIZE, total)
    total_batches = (total + COMPANY_BATCH_SIZE - 1) // COMPANY_BATCH_SIZE

    if key in ("j", "down"):
        if state.selection_idx < end - 1:
            state.selection_idx += 1
        elif state.ai_company_batch_idx < total_batches - 1:
            # Move to next batch
            state.ai_company_batch_idx += 1
            state.selection_idx = state.ai_company_batch_idx * COMPANY_BATCH_SIZE
    elif key in ("k", "up"):
        if state.selection_idx > start:
            state.selection_idx -= 1
        elif state.ai_company_batch_idx > 0:
            # Move to previous batch
            state.ai_company_batch_idx -= 1
            new_start = state.ai_company_batch_idx * COMPANY_BATCH_SIZE
            state.selection_idx = min(new_start + COMPANY_BATCH_SIZE - 1, total - 1)
    elif key in ("<", ",", "left"):
        if state.ai_company_batch_idx > 0:
            state.ai_company_batch_idx -= 1
            state.selection_idx = state.ai_company_batch_idx * COMPANY_BATCH_SIZE
    elif key in (">", ".", "right"):
        if state.ai_company_batch_idx < total_batches - 1:
            state.ai_company_batch_idx += 1
            state.selection_idx = state.ai_company_batch_idx * COMPANY_BATCH_SIZE
    elif key == " ":
        # Toggle highlighted
        if start <= state.selection_idx < end:
            state.ai_company_selected[state.selection_idx] = not state.ai_company_selected[state.selection_idx]
    elif key.isdigit():
        # Toggle by number (1-9, 0=10)
        num = int(key)
        if num == 0:
            num = 10
        idx = start + num - 1
        if idx < end:
            state.ai_company_selected[idx] = not state.ai_company_selected[idx]
    elif key == "a":
        # Select all
        state.ai_company_selected = [True] * total
    elif key == "c":
        # Clear all
        state.ai_company_selected = [False] * total
    elif key == "n":
        # Generate prompt
        selected_companies = [
            state.ai_companies[i]
            for i in range(total)
            if state.ai_company_selected[i]
        ]
        state.ai_prompt = generate_ai_prompt(
            state.ai_keywords,
            state.ai_locations,
            selected_companies
        )
        state.screen = Screen.AI_PROMPT_DISPLAY
    elif key in ("b", "esc"):
        state.screen = Screen.AI_PROMPT_LOCATIONS


def render_ai_prompt_display(state: AppState) -> None:
    """Render the final AI prompt screen."""
    clear_screen()
    render_banner()
    console.print()

    console.print(Panel(
        state.ai_prompt,
        title="[bold]AI Prompt - Copy to ChatGPT/Claude[/bold]",
        box=box.ROUNDED,
        border_style="cyan",
    ))

    console.print()
    console.print("  [cyan]c[/cyan]  Copy to clipboard")
    console.print("  [cyan]e[/cyan]  Edit (go back to keywords)")
    console.print("  [cyan]b[/cyan]  Back to menu")
    render_footer("Press c to copy, b to go back")


def handle_ai_prompt_display(state: AppState, key: str) -> None:
    """Handle AI prompt display screen input."""
    if key == "c":
        if copy_to_clipboard(state.ai_prompt):
            state.message = "Prompt copied to clipboard!"
        else:
            state.message = "Failed to copy - manually select and copy"
    elif key == "e":
        state.screen = Screen.AI_PROMPT_KEYWORDS
    elif key in ("b", "esc", "enter"):
        state.screen = Screen.MAIN_MENU


# ─────────────────────────────────────────────────────────────────────────────
# Main Loop
# ─────────────────────────────────────────────────────────────────────────────


def handle_main_menu(state: AppState, key: str) -> None:
    if key == "o":
        if not state.current_profile or not state.current_profile.urls:
            state.message = "No URLs to open"
            return
        state.prev_screen = Screen.MAIN_MENU
        state.screen = Screen.OPEN_SETTINGS
    elif key == "f":
        if not state.current_profile:
            state.message = "No profile selected"
            return
        if not state.current_profile.search_specs:
            state.message = "No search_specs.json in profile"
            return
        state.prev_screen = Screen.MAIN_MENU
        state.screen = Screen.FETCHING
    elif key == "g":
        if not state.current_profile:
            state.message = "No profile selected"
            return
        init_ai_prompt_builder(state)
        state.prev_screen = Screen.MAIN_MENU
        state.screen = Screen.AI_PROMPT_KEYWORDS
    elif key == "v":
        if not state.current_profile or not state.current_profile.urls:
            state.message = "No URLs to validate"
            return
        state.prev_screen = Screen.MAIN_MENU
        state.screen = Screen.VALIDATING
        start_validation(state)
    elif key == "p":
        if not state.profiles:
            state.message = "No profiles available"
            return
        state.selection_idx = state.profile_idx
        state.prev_screen = Screen.MAIN_MENU
        state.screen = Screen.PROFILE_SELECT
    elif key == "q":
        state.screen = Screen.QUIT


def handle_profile_select(state: AppState, key: str) -> None:
    if key in ("j", "down"):
        state.selection_idx = min(state.selection_idx + 1, len(state.profiles) - 1)
    elif key in ("k", "up"):
        state.selection_idx = max(state.selection_idx - 1, 0)
    elif key == "enter":
        state.profile_idx = state.selection_idx
        state.current_profile.reload_urls()
        state.screen = Screen.MAIN_MENU
    elif key in ("b", "esc"):
        state.screen = Screen.MAIN_MENU
    elif key == "q":
        state.screen = Screen.QUIT


def handle_open_settings(state: AppState) -> None:
    profile = state.current_profile
    max_urls = len(profile.urls)

    tab_limit = read_number("Max tabs to open", min(DEFAULT_TAB_LIMIT, max_urls), max_urls)
    if tab_limit == -1:
        state.screen = Screen.MAIN_MENU
        return
    state.tab_limit = tab_limit

    delay_raw = read_number("Delay between tabs (ms)", int(DEFAULT_DELAY * 1000), 5000)
    if delay_raw == -1:
        state.screen = Screen.MAIN_MENU
        return
    state.delay = delay_raw / 1000.0

    state.screen = Screen.OPENING


def handle_opening(state: AppState) -> None:
    profile = state.current_profile
    urls = profile.urls[: state.tab_limit]

    clear_screen()
    render_banner()
    console.print()

    subprocess.run(["open", "-a", "Google Chrome"], check=False)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("  Opening tabs", total=len(urls))
        for url in urls:
            try:
                open_in_chrome(url)
            except subprocess.CalledProcessError:
                pass
            progress.advance(task)
            if state.delay:
                time.sleep(state.delay)

    state.message = f"Opened {len(urls)} tabs"
    state.screen = Screen.MAIN_MENU


def handle_validating(state: AppState, key: str) -> None:
    if state.validation_status == "running":
        if key == "c":
            state.validation_cancel.set()
    else:
        if key in ("b", "esc", "enter"):
            state.screen = Screen.MAIN_MENU


def handle_fetching(state: AppState) -> None:
    profile = state.current_profile
    render_fetching(state)

    count, error = fetch_jobs_for_profile(profile)
    if error:
        state.message = f"Fetch failed: {error}"
    else:
        profile.reload_urls()
        state.message = f"Fetched {count} jobs"

    state.screen = Screen.MAIN_MENU


def main() -> None:
    cwd = Path.cwd()
    profiles_dir = cwd / "profiles"

    state = AppState()
    state.load_profiles(profiles_dir)

    # Handle command line args
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    if dry_run:
        args.remove("--dry-run")

    if args:
        # Direct file path provided
        file_path = Path(args[0]).expanduser()
        if not file_path.is_absolute():
            file_path = cwd / file_path
        if file_path.exists():
            urls, _, _ = read_urls(file_path)
            console.print(f"Loaded {len(urls)} URLs from {file_path}")
            if dry_run:
                console.print("Dry run complete.")
                return
            # Find or create matching profile
            for i, p in enumerate(state.profiles):
                if p.jobs_file == file_path:
                    state.profile_idx = i
                    break

    if not state.profiles:
        console.print("[red]No profiles found in profiles/ directory[/red]")
        console.print("Create profiles/<name>/jobs.txt to get started")
        return

    # Main event loop
    while state.screen != Screen.QUIT:
        if state.screen == Screen.MAIN_MENU:
            render_main_menu(state)
            key = read_key()
            handle_main_menu(state, key)
        elif state.screen == Screen.PROFILE_SELECT:
            render_profile_select(state)
            key = read_key()
            handle_profile_select(state, key)
        elif state.screen == Screen.OPEN_SETTINGS:
            render_open_settings(state)
            handle_open_settings(state)
        elif state.screen == Screen.OPENING:
            handle_opening(state)
        elif state.screen == Screen.VALIDATING:
            render_validating(state)
            key = read_key()
            handle_validating(state, key)
        elif state.screen == Screen.FETCHING:
            handle_fetching(state)
        elif state.screen == Screen.AI_PROMPT_KEYWORDS:
            render_ai_keywords(state)
            key = read_key()
            handle_ai_keywords(state, key)
        elif state.screen == Screen.AI_PROMPT_LOCATIONS:
            render_ai_locations(state)
            key = read_key()
            handle_ai_locations(state, key)
        elif state.screen == Screen.AI_PROMPT_COMPANIES:
            render_ai_companies(state)
            key = read_key()
            handle_ai_companies(state, key)
        elif state.screen == Screen.AI_PROMPT_DISPLAY:
            render_ai_prompt_display(state)
            key = read_key()
            handle_ai_prompt_display(state, key)

    clear_screen()
    console.print("Bye.")


if __name__ == "__main__":
    main()
