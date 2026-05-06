"""Tests for src/features.py — Phase 3 feature engineering."""

import numpy as np
import pandas as pd
import pytest

from src.features import (
    _rolling_mean_series,
    _rolling_std_series,
    build_player_features,
    rolling_mean_excl_current,
    rolling_std_excl_current,
    ROLLING_FEATURES,
    STD_FEATURES,
    CONTEXT_COLUMNS,
)


# ── TestRollingMeanSeries ───────────────────────────────────────────────

class TestRollingMeanSeries:
    """Tests for the private _rolling_mean_series helper."""

    def test_first_value_is_nan(self):
        s = pd.Series([10, 20, 30])
        result = _rolling_mean_series(s, window=3)
        assert pd.isna(result.iloc[0])

    def test_correct_values(self):
        s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
        result = _rolling_mean_series(s, window=3, min_periods=1)
        # idx 0 → NaN (shift)
        # idx 1 → mean of [10] = 10.0 (only 1 value before shift sees it)
        # idx 2 → mean of [10, 20] = 15.0
        # idx 3 → mean of [20, 30, 40]? No — shift(1) means we see rolling up to idx 2: mean([10,20,30])=20
        # Let's verify step by step:
        # rolling(3, min_periods=1).mean() = [10, 15, 20, 30, 40]
        # .shift(1)                        = [NaN, 10, 15, 20, 30]
        assert pd.isna(result.iloc[0])
        assert result.iloc[1] == pytest.approx(10.0)
        assert result.iloc[2] == pytest.approx(15.0)
        assert result.iloc[3] == pytest.approx(20.0)
        assert result.iloc[4] == pytest.approx(30.0)

    def test_min_periods_respected(self):
        s = pd.Series([10.0, 20.0, 30.0])
        result = _rolling_mean_series(s, window=3, min_periods=3)
        # rolling(3, min_periods=3).mean() = [NaN, NaN, 20]
        # .shift(1)                        = [NaN, NaN, NaN]
        assert result.isna().all()


# ── TestRollingStdSeries ────────────────────────────────────────────────

class TestRollingStdSeries:
    """Tests for the private _rolling_std_series helper."""

    def test_first_value_is_nan(self):
        s = pd.Series([10, 20, 30])
        result = _rolling_std_series(s, window=3)
        assert pd.isna(result.iloc[0])

    def test_constant_input_gives_zero_std(self):
        s = pd.Series([5.0, 5.0, 5.0, 5.0, 5.0])
        result = _rolling_std_series(s, window=3, min_periods=2)
        # All values are the same → std = 0 for windows with >=2 obs
        # rolling(3, min_periods=2).std() = [NaN, 0, 0, 0, 0]
        # .shift(1)                       = [NaN, NaN, 0, 0, 0]
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        assert result.iloc[2] == pytest.approx(0.0)
        assert result.iloc[3] == pytest.approx(0.0)
        assert result.iloc[4] == pytest.approx(0.0)


# ── TestRollingExclCurrentPublicAPI ─────────────────────────────────────

class TestRollingExclCurrentPublicAPI:
    """Tests for the public wrapper functions."""

    def test_rolling_mean_wrapper_matches_helper(self):
        df = pd.DataFrame({"points": [10.0, 20.0, 30.0, 40.0]})
        wrapper_result = rolling_mean_excl_current(df, "points", window=3, min_periods=1)
        helper_result = _rolling_mean_series(df["points"], window=3, min_periods=1)
        pd.testing.assert_series_equal(wrapper_result, helper_result)

    def test_rolling_std_wrapper_matches_helper(self):
        df = pd.DataFrame({"points": [10.0, 20.0, 30.0, 40.0]})
        wrapper_result = rolling_std_excl_current(df, "points", window=3, min_periods=1)
        helper_result = _rolling_std_series(df["points"], window=3, min_periods=1)
        pd.testing.assert_series_equal(wrapper_result, helper_result)


# ── TestNoLeakage ──────────────────────────────────────────────────────

class TestNoLeakage:
    """Verify rolling features never include the current game's data."""

    def test_ppg_last_5_hand_calculated(self, feature_game_logs_df):
        result = build_player_features(feature_game_logs_df)
        p101 = result[result["player_id"] == 101].reset_index(drop=True)
        # Player 101 scores 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31

        # Game 0 (pts=20): ppg_last_5 = NaN (no prior games)
        assert pd.isna(p101.loc[0, "ppg_last_5"])

        # Game 1 (pts=21): ppg_last_5 = mean([20]) = 20.0
        assert p101.loc[1, "ppg_last_5"] == pytest.approx(20.0)

        # Game 5 (pts=25): ppg_last_5 = mean([20,21,22,23,24]) = 22.0
        assert p101.loc[5, "ppg_last_5"] == pytest.approx(22.0)

        # Game 6 (pts=26): ppg_last_5 = mean([21,22,23,24,25]) = 23.0
        assert p101.loc[6, "ppg_last_5"] == pytest.approx(23.0)

    def test_ppg_last_10_hand_calculated(self, feature_game_logs_df):
        result = build_player_features(feature_game_logs_df)
        p101 = result[result["player_id"] == 101].reset_index(drop=True)

        # Game 10 (pts=30): ppg_last_10 = mean([20..29]) = 24.5
        assert p101.loc[10, "ppg_last_10"] == pytest.approx(24.5)

    def test_points_std_last_10_first_is_nan(self, feature_game_logs_df):
        result = build_player_features(feature_game_logs_df)
        p101 = result[result["player_id"] == 101].reset_index(drop=True)
        assert pd.isna(p101.loc[0, "points_std_last_10"])

    def test_current_game_never_in_feature(self, feature_game_logs_df):
        """Row-by-row: ppg_last_5[i] must not be influenced by points[i]."""
        result = build_player_features(feature_game_logs_df)
        for pid in result["player_id"].unique():
            player = result[result["player_id"] == pid].reset_index(drop=True)
            for i in range(1, len(player)):
                # ppg_last_5 at row i should equal the mean of up to 5 prior games
                prior = player.loc[max(0, i - 5): i - 1, "points"]
                expected = prior.mean()
                assert player.loc[i, "ppg_last_5"] == pytest.approx(expected), (
                    f"Leakage at player={pid}, row={i}"
                )


# ── TestRestMetrics ────────────────────────────────────────────────────

class TestRestMetrics:
    """Tests for days_rest and b2b_flag."""

    def test_first_game_default_rest(self, b2b_game_logs_df):
        result = build_player_features(b2b_game_logs_df)
        assert result.iloc[0]["days_rest"] == 7

    def test_correct_rest_spacing(self, b2b_game_logs_df):
        result = build_player_features(b2b_game_logs_df)
        # Jan 1→Jan 2 = 1 day, Jan 2→Jan 5 = 3 days, Jan 5→Jan 6 = 1, Jan 6→Jan 15 = 9
        expected_rest = [7, 1, 3, 1, 9]
        actual_rest = result["days_rest"].tolist()
        assert actual_rest == expected_rest

    def test_clip_at_10(self):
        """Long gap (>10 days) should be clipped to 10."""
        df = pd.DataFrame(
            {
                "game_id": ["G001", "G002"],
                "game_date": pd.to_datetime(["2024-01-01", "2024-02-01"]),
                "player_id": [101, 101],
                "player_name": ["Alice", "Alice"],
                "team_id": [1, 1],
                "opponent_team_id": [2, 2],
                "home_flag": [True, False],
                "points": [20, 25],
                "minutes": [30.0, 32.0],
                "fga": [15, 18],
            }
        )
        result = build_player_features(df)
        assert result.iloc[1]["days_rest"] == 10

    def test_b2b_true(self, b2b_game_logs_df):
        result = build_player_features(b2b_game_logs_df)
        # Rows with 1-day rest are b2b
        b2b_rows = result[result["days_rest"] == 1]
        assert (b2b_rows["b2b_flag"] == 1).all()

    def test_b2b_false_for_normal_rest(self, b2b_game_logs_df):
        result = build_player_features(b2b_game_logs_df)
        non_b2b_rows = result[result["days_rest"] != 1]
        assert (non_b2b_rows["b2b_flag"] == 0).all()

    def test_first_game_not_b2b(self, b2b_game_logs_df):
        result = build_player_features(b2b_game_logs_df)
        assert result.iloc[0]["b2b_flag"] == 0


# ── TestOptionalColumns ────────────────────────────────────────────────

class TestOptionalColumns:
    """Tests for handling optional source and context columns."""

    def test_usage_skipped_when_absent(self, feature_game_logs_df):
        result = build_player_features(feature_game_logs_df)
        assert "usage_last_5" not in result.columns

    def test_ts_skipped_when_absent(self, feature_game_logs_df):
        result = build_player_features(feature_game_logs_df)
        assert "ts_last_5" not in result.columns

    def test_usage_computed_when_present(self, feature_game_logs_df):
        df = feature_game_logs_df.copy()
        df["usage"] = 25.0  # constant usage rate
        result = build_player_features(df)
        assert "usage_last_5" in result.columns

    def test_ts_computed_when_present(self, feature_game_logs_df):
        df = feature_game_logs_df.copy()
        df["ts"] = 0.55  # constant true shooting
        result = build_player_features(df)
        assert "ts_last_5" in result.columns

    def test_context_columns_added_as_na(self, feature_game_logs_df):
        """Context columns that don't exist in input get added as NA."""
        # Remove home_flag to test it gets re-added
        df = feature_game_logs_df.drop(columns=["home_flag"])
        result = build_player_features(df)
        for col in CONTEXT_COLUMNS:
            assert col in result.columns


# ── TestBuildPlayerFeaturesShape ───────────────────────────────────────

class TestBuildPlayerFeaturesShape:
    """Tests for output shape and properties."""

    def test_row_count_preserved(self, feature_game_logs_df):
        result = build_player_features(feature_game_logs_df)
        assert len(result) == len(feature_game_logs_df)

    def test_expected_columns_present(self, feature_game_logs_df):
        result = build_player_features(feature_game_logs_df)
        expected = {"ppg_last_5", "ppg_last_10", "min_last_5", "shots_last_5",
                    "points_std_last_10", "days_rest", "b2b_flag"}
        assert expected.issubset(set(result.columns))

    def test_sorted_by_player_and_date(self, feature_game_logs_df):
        result = build_player_features(feature_game_logs_df)
        assert result["player_id"].is_monotonic_increasing or (
            result.groupby("player_id")["game_date"].apply(
                lambda s: s.is_monotonic_increasing
            ).all()
        )

    def test_no_mutation_of_input(self, feature_game_logs_df):
        original = feature_game_logs_df.copy()
        build_player_features(feature_game_logs_df)
        pd.testing.assert_frame_equal(feature_game_logs_df, original)

    def test_min_periods_parameter(self, feature_game_logs_df):
        result = build_player_features(feature_game_logs_df, min_periods=5)
        p101 = result[result["player_id"] == 101].reset_index(drop=True)
        # With min_periods=5, first 5 rows should be NaN for ppg_last_5
        # (shift means we need 5 prior values → rows 0-4 are NaN, row 5 gets a value)
        for i in range(5):
            assert pd.isna(p101.loc[i, "ppg_last_5"])
        assert not pd.isna(p101.loc[5, "ppg_last_5"])


# ── TestPlayerIsolation ────────────────────────────────────────────────

class TestPlayerIsolation:
    """Verify features are computed independently per player."""

    def test_features_independent_per_player(self, feature_game_logs_df):
        result = build_player_features(feature_game_logs_df)
        p101 = result[result["player_id"] == 101].reset_index(drop=True)
        p102 = result[result["player_id"] == 102].reset_index(drop=True)

        # Player 101 scores increase (20→31), player 102 decrease (30→19)
        # At game index 5, ppg_last_5:
        #   p101 = mean([20,21,22,23,24]) = 22.0
        #   p102 = mean([30,29,28,27,26]) = 28.0
        assert p101.loc[5, "ppg_last_5"] == pytest.approx(22.0)
        assert p102.loc[5, "ppg_last_5"] == pytest.approx(28.0)
