"""Tests for src/grok_client.py — Phase 4 Perplexity sportsbook line fetcher."""

import json
import logging
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests

from src.grok_client import (
    PerplexityAPIError,
    call_perplexity_api,
    fetch_lines_for_date,
    load_prompt_template,
    parse_lines_response,
)


VALID_LINE = {
    "player_name": "LeBron James",
    "team": "LAL",
    "opponent": "BOS",
    "game_datetime_local": "2025-01-15T19:30:00-05:00",
    "sportsbook_line": 25.5,
    "sportsbook_name": "DraftKings",
}

VALID_LINE_2 = {
    "player_name": "Jayson Tatum",
    "team": "BOS",
    "opponent": "LAL",
    "game_datetime_local": "2025-01-15T19:30:00-05:00",
    "sportsbook_line": 27.5,
    "sportsbook_name": "FanDuel",
}


# ── TestLoadPromptTemplate ────────────────────────────────────────────────


class TestLoadPromptTemplate:
    """Tests for load_prompt_template."""

    def test_loads_existing_template(self):
        template = load_prompt_template("fetch_lines.txt")
        assert isinstance(template, str)
        assert "{date}" in template

    def test_nonexistent_template_raises(self):
        with pytest.raises(FileNotFoundError):
            load_prompt_template("nonexistent_template.txt")


# ── TestParseLineResponse ─────────────────────────────────────────────────


class TestParseLineResponse:
    """Tests for parse_lines_response."""

    def test_valid_array(self):
        raw = json.dumps([VALID_LINE, VALID_LINE_2])
        result = parse_lines_response(raw)
        assert len(result) == 2
        assert result[0]["player_name"] == "LeBron James"
        assert result[1]["sportsbook_line"] == 27.5

    def test_missing_field_skipped(self, caplog):
        bad_row = {k: v for k, v in VALID_LINE.items() if k != "sportsbook_line"}
        raw = json.dumps([bad_row, VALID_LINE_2])
        with caplog.at_level(logging.WARNING):
            result = parse_lines_response(raw)
        assert len(result) == 1
        assert result[0]["player_name"] == "Jayson Tatum"
        assert "missing required field" in caplog.text

    def test_invalid_sportsbook_line_type_skipped(self, caplog):
        bad_row = {**VALID_LINE, "sportsbook_line": "not_a_number"}
        raw = json.dumps([bad_row])
        with caplog.at_level(logging.WARNING):
            result = parse_lines_response(raw)
        assert len(result) == 0
        assert "sportsbook_line" in caplog.text

    def test_empty_array(self):
        result = parse_lines_response("[]")
        assert result == []

    def test_malformed_json_raises(self):
        with pytest.raises(ValueError, match="Malformed JSON"):
            parse_lines_response("not json at all {{{")

    def test_extra_fields_preserved(self):
        row_with_extra = {**VALID_LINE, "over_odds": -110}
        raw = json.dumps([row_with_extra])
        result = parse_lines_response(raw)
        assert len(result) == 1
        assert result[0]["over_odds"] == -110

    def test_wrapped_object_with_array(self):
        raw = json.dumps({"lines": [VALID_LINE]})
        result = parse_lines_response(raw)
        assert len(result) == 1
        assert result[0]["player_name"] == "LeBron James"

    def test_integer_sportsbook_line_valid(self):
        row = {**VALID_LINE, "sportsbook_line": 25}
        raw = json.dumps([row])
        result = parse_lines_response(raw)
        assert len(result) == 1
        assert result[0]["sportsbook_line"] == 25


# ── TestCallPerplexityAPI ─────────────────────────────────────────────────


class TestCallPerplexityAPI:
    """Tests for call_perplexity_api."""

    def _mock_response(self, content, status_code=200):
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = status_code
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": content}}]
        }
        mock_resp.raise_for_status.return_value = None
        return mock_resp

    @patch.dict("os.environ", {"PERPLEXITY_API_KEY": "test-key"})
    @patch("src.grok_client.requests.post")
    def test_successful_response(self, mock_post):
        mock_post.return_value = self._mock_response('{"data": []}')
        result = call_perplexity_api("test prompt")
        assert result == '{"data": []}'
        mock_post.assert_called_once()

    @patch.dict("os.environ", {"PERPLEXITY_API_KEY": "test-key"})
    @patch("src.grok_client.requests.post")
    def test_http_error_raises(self, mock_post):
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 400
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_resp
        )
        mock_post.return_value = mock_resp
        with pytest.raises(PerplexityAPIError, match="HTTP error"):
            call_perplexity_api("test prompt")

    @patch.dict("os.environ", {"PERPLEXITY_API_KEY": "test-key"})
    @patch("src.grok_client.requests.post")
    def test_empty_choices_raises(self, mock_post):
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": []}
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp
        with pytest.raises(PerplexityAPIError, match="no choices"):
            call_perplexity_api("test prompt")

    @patch.dict("os.environ", {"PERPLEXITY_API_KEY": "test-key"})
    @patch("src.grok_client.time.sleep")
    @patch("src.grok_client.requests.post")
    def test_retry_on_500(self, mock_post, mock_sleep):
        # First two calls return 500, third succeeds
        error_resp = MagicMock(spec=requests.Response)
        error_resp.status_code = 500
        http_error = requests.exceptions.HTTPError(response=error_resp)
        error_resp.raise_for_status.side_effect = http_error

        success_resp = self._mock_response('{"result": "ok"}')

        mock_post.side_effect = [error_resp, error_resp, success_resp]
        result = call_perplexity_api("test prompt")
        assert result == '{"result": "ok"}'
        assert mock_post.call_count == 3
        assert mock_sleep.call_count == 2

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_api_key_raises(self):
        with pytest.raises(PerplexityAPIError, match="PERPLEXITY_API_KEY"):
            call_perplexity_api("test prompt")


# ── TestFetchLinesForDate ─────────────────────────────────────────────────


class TestFetchLinesForDate:
    """Tests for fetch_lines_for_date orchestrator."""

    @patch("src.grok_client.call_perplexity_api")
    def test_returns_dataframe_with_correct_columns(self, mock_api):
        mock_api.return_value = json.dumps([VALID_LINE, VALID_LINE_2])
        df = fetch_lines_for_date("2025-01-15")

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        expected_cols = {
            "player_name", "team", "opponent", "game_datetime_local",
            "sportsbook_line", "sportsbook_name", "game_date",
        }
        assert set(df.columns) >= expected_cols

    @patch("src.grok_client.call_perplexity_api")
    def test_game_date_column_added(self, mock_api):
        mock_api.return_value = json.dumps([VALID_LINE])
        df = fetch_lines_for_date("2025-01-15")
        assert (df["game_date"] == "2025-01-15").all()

    @patch("src.grok_client.call_perplexity_api")
    def test_correct_dtypes(self, mock_api):
        mock_api.return_value = json.dumps([VALID_LINE])
        df = fetch_lines_for_date("2025-01-15")
        assert df["sportsbook_line"].dtype in ("float64", "int64")
        assert df["player_name"].dtype == "object"

    @patch("src.grok_client.call_perplexity_api")
    def test_empty_response_returns_empty_df(self, mock_api):
        mock_api.return_value = "[]"
        df = fetch_lines_for_date("2025-01-15")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
        assert "game_date" in df.columns
