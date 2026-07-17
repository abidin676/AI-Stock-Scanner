from pathlib import Path

import pandas as pd
import pytest

from alert_engine import empty_seed_alerts, generate_seed_alerts, valid_seed_candidates
from ai_decision_engine import build_ai_decisions
from candidate_eligibility import apply_eligibility_policy
from config import MAX_FRESH_CROSS_DAYS
from fresh_cross_policy import (
    apply_fresh_cross_policy,
    evaluate_fresh_cross_policy,
)
from views.scanner import top_seed_opportunities


def policy_row(**overrides):
    row = {
        "Symbol": "FRESH.BK",
        "Market": "SET",
        "EMA9": 11,
        "EMA20": 10,
        "DaysSinceEMA9CrossEMA20": 0,
        "LatestPriceDate": "2026-07-17",
        "CrossDate": "2026-07-17",
        "CrossAgeSource": "days_since_bullish_ema_cross",
        "PreviousEMA9": 9.8,
        "PreviousEMA20": 10,
        "BullishCrossEvent": True,
        "LifecycleState": "SEED",
        "StrategySignal": "SEED BUY",
        "RecommendedAction": "Review First",
        "PriorityRank": 1,
        "PriorityScore": 100,
        "SeedScore": 100,
        "FreshnessScore": 100,
        "ExpansionScore": 0,
        "RR": 5,
        "EntryPrice": 10,
        "StopPrice": 9,
        "TargetPrice": 15,
        "RVOL": 1.5,
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize("cross_age", [0, 1, 2])
def test_policy_accepts_only_configured_fresh_ages(cross_age):
    result = evaluate_fresh_cross_policy(
        policy_row(DaysSinceEMA9CrossEMA20=cross_age)
    )

    assert result.eligible is True
    assert result.status == "FRESH_CROSS"


@pytest.mark.parametrize(
    ("overrides", "status", "label"),
    [
        ({"DaysSinceEMA9CrossEMA20": 3}, "STALE_CROSS", "Cross เก่า"),
        ({"DaysSinceEMA9CrossEMA20": 5}, "STALE_CROSS", "Cross เก่า"),
        ({"DaysSinceEMA9CrossEMA20": None}, "NO_CROSS", "ยังไม่ Cross"),
        (
            {
                "EMA9": 9,
                "EMA20": 10,
                "DaysSinceEMA9CrossEMA20": 1,
            },
            "EMA9_NOT_ABOVE",
            "EMA9 ต่ำกว่า EMA20",
        ),
    ],
)
def test_policy_rejects_non_fresh_states_with_explicit_labels(
    overrides,
    status,
    label,
):
    result = evaluate_fresh_cross_policy(policy_row(**overrides))

    assert result.eligible is False
    assert result.status == status
    assert result.status_label == label


def test_alert_candidates_cannot_be_revived_by_score_or_volume():
    candidates = pd.DataFrame(
        [
            policy_row(Symbol="TODAY.BK"),
            policy_row(
                Symbol="STALE.BK",
                DaysSinceEMA9CrossEMA20=10,
                PriorityScore=999,
                SeedScore=999,
                RVOL=99,
            ),
        ]
    )

    valid = valid_seed_candidates(candidates)
    alerts = generate_seed_alerts(
        priority_results=candidates,
        scan_date="2026-07-17",
        history=empty_seed_alerts(),
        source_file=Path("priority_results.csv"),
        force=True,
    )

    assert valid["Symbol"].tolist() == ["TODAY.BK"]
    assert alerts["Symbol"].tolist() == ["TODAY.BK"]
    assert alerts.iloc[0]["CrossAge"] == "Today"
    assert alerts.iloc[0]["CrossStatus"] == "Fresh Cross"


def test_stale_cross_cannot_reach_ai_buy_or_prepare_decisions():
    ranked = apply_eligibility_policy(
        pd.DataFrame(
            [
                policy_row(
                    Symbol="STALE.BK",
                    DaysSinceEMA9CrossEMA20=10,
                    PriorityScore=999,
                    SeedScore=999,
                    RVOL=99,
                )
            ]
        )
    )
    decisions = build_ai_decisions(ranked)

    assert ranked.iloc[0]["QueueClass"] == "IGNORE"
    assert decisions.iloc[0]["AIDecision"] not in {"BUY", "PREPARE"}


def test_top_five_seed_surface_uses_the_same_fresh_cross_gate():
    candidates = pd.DataFrame(
        [
            policy_row(Symbol="FRESH.BK", PriorityRank=2),
            policy_row(
                Symbol="STALE.BK",
                DaysSinceEMA9CrossEMA20=10,
                PriorityRank=1,
                PriorityScore=999,
            ),
        ]
    )

    top = top_seed_opportunities(candidates, "SET", limit=5)

    assert top["Symbol"].tolist() == ["FRESH.BK"]


def test_apply_policy_keeps_stale_rows_for_show_all_diagnostics():
    data = apply_fresh_cross_policy(
        pd.DataFrame(
            [
                policy_row(
                    Symbol="STALE.BK",
                    DaysSinceEMA9CrossEMA20=10,
                )
            ]
        )
    )

    assert data["Symbol"].tolist() == ["STALE.BK"]
    assert not bool(data.iloc[0]["FreshCrossEligible"])
    assert data.iloc[0]["CrossAgeLabel"] == "10D"
    assert data.iloc[0]["FreshCrossStatusLabel"] == "Cross เก่า"


def test_policy_never_falls_back_to_today_from_ema_above_or_legacy_alias():
    result = evaluate_fresh_cross_policy(
        policy_row(
            DaysSinceEMA9CrossEMA20=None,
            DaysSinceEMACross=0,
            EMABullishCrossToday=True,
            EMA9AboveEMA20=True,
            CrossDate=None,
        )
    )

    assert result.age is None
    assert result.eligible is False
    assert result.status == "NO_CROSS"
    assert result.age_label == "-"


def test_permanent_policy_default_is_two_trading_days():
    assert MAX_FRESH_CROSS_DAYS == 2
