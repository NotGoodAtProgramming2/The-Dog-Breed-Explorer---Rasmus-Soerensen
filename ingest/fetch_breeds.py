"""Fetches breeds from the Dog API and stores them as raw JSON: one dated
snapshot per run, plus a "latest.json" pointer to the newest one. Idempotent,
and never overwrites good data with a bad/partial response. See DECISIONS.md."""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

API_URL = "https://api.thedogapi.com/v1/breeds"
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
MAX_ATTEMPTS = 3
TIMEOUT_SECONDS = 15


def fetch_breeds() -> list:
    """Calls the Dog API with a few retries, and returns the parsed JSON list."""
    api_key = os.environ.get("DOG_API_KEY")
    if not api_key:
        raise RuntimeError(
            "DOG_API_KEY environment variable is not set. "
            "Get a free key at https://www.thedogapi.com/signup"
        )
    headers = {"x-api-key": api_key}

    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(API_URL, headers=headers, timeout=TIMEOUT_SECONDS)
            response.raise_for_status()
            data = response.json()
            validate(data)
            return data
        except (requests.RequestException, ValueError) as error:
            last_error = error
            print(f"Attempt {attempt}/{MAX_ATTEMPTS} failed: {error}", file=sys.stderr)
            if attempt < MAX_ATTEMPTS:
                time.sleep(2 ** attempt)  # 2s, 4s backoff between retries

    raise RuntimeError(f"Giving up after {MAX_ATTEMPTS} attempts: {last_error}")


def validate(data) -> None:
    """Fail here, not downstream, on an empty or malformed response."""
    if not isinstance(data, list) or len(data) == 0:
        raise ValueError("Response is not a non-empty list of breeds")
    first = data[0]
    if "id" not in first or "name" not in first:
        raise ValueError("Breed records are missing expected 'id'/'name' fields")


def save(data: list) -> Path:
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dated_dir = RAW_DIR / run_date
    dated_dir.mkdir(parents=True, exist_ok=True)
    dated_path = dated_dir / "breeds.json"
    dated_path.write_text(json.dumps(data, indent=2))

    # "latest.json" always mirrors the newest snapshot; dbt reads from this
    # fixed path so it never has to guess which dated folder is newest.
    latest_path = RAW_DIR / "latest.json"
    latest_path.write_text(json.dumps(data, indent=2))

    return dated_path


def main():
    data = fetch_breeds()
    dated_path = save(data)
    print(f"Fetched {len(data)} breeds -> {dated_path} (and data/raw/latest.json)")


if __name__ == "__main__":
    main()
