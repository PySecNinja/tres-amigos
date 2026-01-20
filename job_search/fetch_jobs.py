#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote_plus

import httpx

def load_config(path: Path) -> Dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"ERROR: Config not found: {path}")
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"ERROR: Invalid JSON in {path}: {exc}")
        sys.exit(1)

def normalize_terms(terms: Optional[List[str]]) -> List[str]:
    if not terms:
        return []
    return [t.strip().lower() for t in terms if t.strip()]

def matches_terms(text: str, terms: List[str]) -> bool:
    if not terms:
        return True
    lower = text.lower()
    return any(term in lower for term in terms)

def matches_job(title: str, location: str, keywords: List[str], locations: List[str]) -> bool:
    if keywords and not (matches_terms(title, keywords) or matches_terms(location, keywords)):
        return False
    if locations and not matches_terms(location, locations):
        return False
    return True

def fetch_greenhouse(client: httpx.Client, company: str) -> List[Dict]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
    resp = client.get(url, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data.get("jobs", [])

def fetch_lever(client: httpx.Client, company: str) -> List[Dict]:
    url = f"https://api.lever.co/v0/postings/{company}?mode=json"
    resp = client.get(url, timeout=20)
    resp.raise_for_status()
    return resp.json()

def extract_greenhouse_jobs(jobs: List[Dict], keywords: List[str], locations: List[str], max_results: Optional[int]) -> List[str]:
    results = []
    for job in jobs:
        title = job.get("title", "")
        location = job.get("location", {}).get("name", "")
        url = job.get("absolute_url", "")
        if not url:
            continue
        if matches_job(title, location, keywords, locations):
            results.append(url)
        if max_results and len(results) >= max_results:
            break
    return results

def extract_lever_jobs(jobs: List[Dict], keywords: List[str], locations: List[str], max_results: Optional[int]) -> List[str]:
    results = []
    for job in jobs:
        title = job.get("text", "")
        categories = job.get("categories", {})
        location = categories.get("location", "")
        url = job.get("hostedUrl", "")
        if not url:
            continue
        if matches_job(title, location, keywords, locations):
            results.append(url)
        if max_results and len(results) >= max_results:
            break
    return results

def build_google_jobs_url(query: str) -> str:
    encoded = quote_plus(query)
    return f"https://www.google.com/search?q={encoded}&ibp=htl;jobs"

def unique_preserve_order(urls: List[str]) -> List[str]:
    seen = set()
    ordered = []
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        ordered.append(url)
    return ordered

def main() -> None:
    cwd = Path.cwd()
    config_path = cwd / "search_specs.json"
    output_dir = cwd

    # Parse arguments: fetch_jobs.py [config_path] [output_dir]
    if len(sys.argv) >= 2:
        config_path = Path(sys.argv[1]).expanduser()
        if not config_path.is_absolute():
            config_path = cwd / config_path
    if len(sys.argv) >= 3:
        output_dir = Path(sys.argv[2]).expanduser()
        if not output_dir.is_absolute():
            output_dir = cwd / output_dir

    config = load_config(config_path)
    sources = config.get("sources", [])
    # If output_dir is a profile directory, write to jobs.txt there
    # Otherwise use the config's output_file setting
    if output_dir != cwd:
        output_path = output_dir / "jobs.txt"
    else:
        output_file = config.get("output_file", "jobs_fetched.txt")
        output_path = cwd / output_file

    if not sources:
        print("ERROR: No sources configured.")
        sys.exit(1)

    all_urls: List[str] = []
    with httpx.Client(headers={"User-Agent": "job-search-fetcher/1.0"}) as client:
        for source in sources:
            provider = source.get("provider", "").strip().lower()
            keywords = normalize_terms(source.get("keywords"))
            locations = normalize_terms(source.get("locations"))
            max_results = source.get("max_results")

            if provider == "greenhouse":
                company = source.get("company")
                if not company:
                    print("WARN: greenhouse source missing company")
                    continue
                try:
                    jobs = fetch_greenhouse(client, company)
                except httpx.HTTPError as exc:
                    print(f"WARN: greenhouse fetch failed for {company}: {exc}")
                    continue
                urls = extract_greenhouse_jobs(jobs, keywords, locations, max_results)
                all_urls.extend(urls)
            elif provider == "lever":
                company = source.get("company")
                if not company:
                    print("WARN: lever source missing company")
                    continue
                try:
                    jobs = fetch_lever(client, company)
                except httpx.HTTPError as exc:
                    print(f"WARN: lever fetch failed for {company}: {exc}")
                    continue
                urls = extract_lever_jobs(jobs, keywords, locations, max_results)
                all_urls.extend(urls)
            elif provider == "google_jobs":
                query = source.get("query")
                if not query:
                    print("WARN: google_jobs source missing query")
                    continue
                all_urls.append(build_google_jobs_url(query))
            else:
                print(f"WARN: Unknown provider: {provider}")

    all_urls = unique_preserve_order(all_urls)
    if not all_urls:
        print("No URLs found.")
        return

    output_path.write_text("\n".join(all_urls) + "\n", encoding="utf-8")
    print(f"Wrote {len(all_urls)} URLs to {output_path}")

if __name__ == "__main__":
    main()
