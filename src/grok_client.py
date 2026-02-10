"""Perplexity API client for fetching sportsbook lines.

Provides functions to load prompt templates, call the Perplexity chat
completions API, parse JSON responses into validated dicts, and orchestrate
daily line fetching into a DataFrame.
"""

import json
import logging
import os
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_LINE_FIELDS = {
    "player_name": str,
    "team": str,
    "opponent": str,
    "game_datetime_local": str,
    "sportsbook_line": (int, float),
    "sportsbook_name": str,
}

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
DEFAULT_MODEL = "sonar-pro"
DEFAULT_TEMPERATURE = 0.0
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2


class PerplexityAPIError(Exception):
    """Raised when the Perplexity API returns an error or unexpected response."""


def load_prompt_template(template_name: str) -> str:
    """Read a prompt template from the grok_prompts directory.

    Args:
        template_name: Filename of the template (e.g. "fetch_lines.txt").

    Returns:
        Raw template string contents.

    Raises:
        FileNotFoundError: If the template file does not exist.
    """
    template_path = PROJECT_ROOT / "grok_prompts" / template_name
    return template_path.read_text()


def call_perplexity_api(
    prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """Call the Perplexity chat completions API and return the response content.

    Args:
        prompt: The user message to send.
        model: Model identifier (default: "sonar-pro").
        temperature: Sampling temperature (default: 0.0).
        timeout: Request timeout in seconds (default: 30).

    Returns:
        Raw content string from the API response.

    Raises:
        PerplexityAPIError: On HTTP errors, missing API key, or unexpected response.
    """
    api_key = os.environ.get("PERPLEXITY_API_KEY")
    if not api_key:
        raise PerplexityAPIError("PERPLEXITY_API_KEY environment variable is not set")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a sports data assistant."},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }

    last_exception = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(
                PERPLEXITY_API_URL,
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise PerplexityAPIError("API response contained no choices")

            content = choices[0].get("message", {}).get("content")
            if not content:
                raise PerplexityAPIError("API response contained no message content")

            return content

        except requests.exceptions.HTTPError as exc:
            last_exception = exc
            status = exc.response.status_code if exc.response is not None else None
            if status is not None and status >= 500 and attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF_BASE ** attempt
                logger.warning(
                    "Perplexity API returned %s, retrying in %ss (attempt %d/%d)",
                    status, wait, attempt, MAX_RETRIES,
                )
                time.sleep(wait)
                continue
            raise PerplexityAPIError(f"HTTP error from Perplexity API: {exc}") from exc

        except requests.exceptions.RequestException as exc:
            raise PerplexityAPIError(f"Request failed: {exc}") from exc

    raise PerplexityAPIError(f"Max retries exceeded: {last_exception}") from last_exception


def parse_lines_response(raw_json: str) -> list[dict]:
    """Parse and validate a JSON string of sportsbook lines.

    Expects a JSON array of objects (or a JSON object with a key containing
    an array). Each object must have the required fields defined in
    REQUIRED_LINE_FIELDS. Rows with missing or incorrectly typed fields are
    skipped with a warning.

    Args:
        raw_json: Raw JSON string from the API.

    Returns:
        List of validated line dicts.

    Raises:
        ValueError: If the JSON string is malformed.
    """
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed JSON: {exc}") from exc

    # Handle both a raw array and an object wrapping an array
    if isinstance(parsed, dict):
        # Find the first list value in the dict
        for value in parsed.values():
            if isinstance(value, list):
                parsed = value
                break
        else:
            raise ValueError("JSON object does not contain an array of lines")

    if not isinstance(parsed, list):
        raise ValueError(f"Expected JSON array, got {type(parsed).__name__}")

    valid_rows = []
    for i, row in enumerate(parsed):
        if not isinstance(row, dict):
            logger.warning("Row %d is not a dict, skipping", i)
            continue

        skip = False
        for field, expected_type in REQUIRED_LINE_FIELDS.items():
            if field not in row:
                logger.warning("Row %d missing required field '%s', skipping", i, field)
                skip = True
                break
            if not isinstance(row[field], expected_type):
                logger.warning(
                    "Row %d field '%s' has type %s, expected %s, skipping",
                    i, field, type(row[field]).__name__, expected_type,
                )
                skip = True
                break

        if not skip:
            valid_rows.append(row)

    return valid_rows


def fetch_lines_for_date(date_str: str) -> pd.DataFrame:
    """Fetch sportsbook lines for a given date and return as a DataFrame.

    Orchestrates the full pipeline: loads the prompt template, formats it
    with the target date, calls the Perplexity API, parses the response, and
    returns a DataFrame with the PRD 9.3 schema plus a game_date column.

    Args:
        date_str: Target date string (e.g. "2025-01-15").

    Returns:
        DataFrame with columns: player_name, team, opponent,
        game_datetime_local, sportsbook_line, sportsbook_name, game_date.
    """
    template = load_prompt_template("fetch_lines.txt")
    prompt = template.format(date=date_str)

    logger.info("Fetching sportsbook lines for %s", date_str)
    raw_response = call_perplexity_api(prompt)
    lines = parse_lines_response(raw_response)

    if not lines:
        logger.warning("No valid lines returned for %s", date_str)
        return pd.DataFrame(
            columns=list(REQUIRED_LINE_FIELDS.keys()) + ["game_date"]
        )

    df = pd.DataFrame(lines)
    df["game_date"] = date_str
    return df
