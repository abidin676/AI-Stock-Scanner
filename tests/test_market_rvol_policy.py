import pandas as pd
import pytest

from ai_decision_engine import build_ai_decisions, make_ai_decision
from alert_engine import valid_seed_candidates
from candidate_eligibility import (
    apply_eligibility_policy,
    evaluate_candidate_eligibility,
)
from config import (
    MARKET_RVOL_THRESHOLDS,
    rvol_action_for_market,
    rvol_thresholds_for_market,
)
from priority_engine import apply_priority_mode
from views.scanner import (
    build_simple_dashboard_sections,
    prepare_daily_candidates,
    simple_near_buy_table,
    simple_pick_table,
)


def actionable_row(market, rvol, **overrides):
    symbol = "USA_TEST" if market == "USA" else "SET_TEST.BK"
    row = {
        "Symbol": symbol,
        "Market": market,
        "EMA9": 10.2,
        "EMA20": 10.0,
        "EMA50": 9.5,
        "PreviousEMA9": 9.8,
        "PreviousEMA20": 10.0,
        "BullishCrossEvent": True,
        "DaysSinceEMA9CrossEMA20": 0,
        "LatestPriceDate": "2026-07-17",
        "CrossDate": "2026-07-17",
        "CrossAgeSource": "days_since_bullish_ema_cross",
        "EMA20Improving": True,
        "DaysSinceEMA20SlopeTurnPositive": 1,
        "LifecycleState": "SEED",
        "StrategySignal": "SEED BUY",
        "StrategySetup": "Early Reversal",
        "RecommendedAction": "Buy",
        "PriorityAction": "Review First",
        "AIDecision": "BUY",
        "AIConfidence": 90,
        "PriorityScore": 95,
        "OpportunityScore": 85,
        "StrategyScore": 85,
        "SeedScore": 95,
        "FreshnessScore": 90,
        "MarketQualityScore": 70,
        "MarketQualityLabel": "Healthy",
        "Price": 10,
        "EntryPrice": 10,
        "StopPrice": 9,
        "TargetPrice": 13,
        "Stop": 9,
        "Target": 13,
        "RiskPct": 3,
        "RR": 3,
        "RiskApproved": True,
        "RSI": 55,
        "RVOL": rvol,
        "ExpansionScore": 10,
    }
    row.update(overrides)
    return row


def test_market_rvol_thresholds_are_central_and_distinct():
    assert MARKET_RVOL_THRESHOLDS == {
        "SET": {"PREPARE": 1.0, "BUY": 1.5},
        "USA": {"PREPARE": 0.8, "BUY": 1.2},
    }
    assert rvol_thresholds_for_market("USA") != rvol_thresholds_for_market("SET")


@pytest.mark.parametrize("rvol", [0.8, 0.99, 1.19])
def test_usa_prepare_range_uses_usa_threshold(rvol):
    row = actionable_row("USA", rvol)

    eligibility = evaluate_candidate_eligibility(row)
    ai = make_ai_decision(row)
    sections = build_simple_dashboard_sections(pd.DataFrame([row]))

    assert rvol_action_for_market("USA", rvol) == "PREPARE"
    assert eligibility.queue_class == "PREPARE"
    assert ai["AIDecision"] == "PREPARE"
    assert sections["near_buy"]["Symbol"].tolist() == ["USA_TEST"]
    assert sections["buy_now"].empty


@pytest.mark.parametrize("rvol", [1.2, 1.5, 2.0])
def test_usa_buy_threshold_is_1_2(rvol):
    row = actionable_row("USA", rvol)

    assert evaluate_candidate_eligibility(row).queue_class == "BUY"
    assert make_ai_decision(row)["AIDecision"] == "BUY"
    assert build_simple_dashboard_sections(pd.DataFrame([row]))["buy_now"][
        "Symbol"
    ].tolist() == ["USA_TEST"]


@pytest.mark.parametrize("rvol", [1.0, 1.2, 1.49])
def test_set_prepare_range_remains_stricter(rvol):
    row = actionable_row("SET", rvol)

    assert rvol_action_for_market("SET", rvol) == "PREPARE"
    assert evaluate_candidate_eligibility(row).queue_class == "PREPARE"
    assert make_ai_decision(row)["AIDecision"] == "PREPARE"


@pytest.mark.parametrize("rvol", [1.5, 2.0])
def test_set_buy_threshold_remains_1_5(rvol):
    row = actionable_row("SET", rvol)

    assert evaluate_candidate_eligibility(row).queue_class == "BUY"
    assert make_ai_decision(row)["AIDecision"] == "BUY"


def test_usa_threshold_does_not_relax_set():
    usa = evaluate_candidate_eligibility(actionable_row("USA", 0.9))
    set_result = evaluate_candidate_eligibility(actionable_row("SET", 0.9))

    assert usa.queue_class == "PREPARE"
    assert set_result.queue_class == "IGNORE"
    assert any("SET PREPARE threshold 1x" in reason for reason in set_result.blocking_reasons)


def test_dashboard_reason_names_current_and_usa_buy_rvol():
    sections = build_simple_dashboard_sections(
        pd.DataFrame([actionable_row("USA", 0.99)])
    )
    table = simple_near_buy_table(sections["near_buy"])

    assert table.iloc[0]["Next Action"] == (
        "รอ RVOL จาก 0.99x ให้ถึง 1.2x เพื่อเป็นซื้อได้"
    )
    assert sections["near_buy"].iloc[0]["_SimpleReason"] == (
        "รอ RVOL จาก 0.99x ให้ถึง 1.2x เพื่อเป็นซื้อได้"
    )


def test_priority_and_alert_layers_use_market_prepare_threshold():
    rows = pd.DataFrame(
        [
            actionable_row("USA", 0.8, Symbol="USA_ALERT"),
            actionable_row("SET", 0.8, Symbol="SET_ALERT.BK"),
        ]
    )
    priority = apply_priority_mode(rows, "Seed First")
    by_symbol = priority.set_index("Symbol")
    alerts = valid_seed_candidates(rows)

    assert by_symbol.loc["USA_ALERT", "RVOLAction"] == "PREPARE"
    assert by_symbol.loc["USA_ALERT", "RVOLPrepareThreshold"] == 0.8
    assert by_symbol.loc["USA_ALERT", "RVOLBuyThreshold"] == 1.2
    assert by_symbol.loc["SET_ALERT.BK", "RVOLAction"] == "WATCH"
    assert alerts["Symbol"].tolist() == ["USA_ALERT"]


@pytest.mark.parametrize(
    "overrides",
    [
        {
            "DaysSinceEMA9CrossEMA20": 5,
            "CrossDate": "2026-07-10",
            "BullishCrossEvent": False,
        },
        {
            "LifecycleState": "EXTENDED",
            "StrategySignal": "EXTENDED",
            "ExpansionScore": 100,
        },
    ],
)
def test_old_cross_and_extended_never_pass_even_with_high_rvol(overrides):
    rows = pd.DataFrame([actionable_row("USA", 99, **overrides)])
    eligible = apply_eligibility_policy(rows)
    decisions = build_ai_decisions(eligible)
    sections = build_simple_dashboard_sections(rows)

    assert eligible.iloc[0]["QueueClass"] == "IGNORE"
    assert decisions.iloc[0]["AIDecision"] not in {"BUY", "PREPARE"}
    assert sections["buy_now"].empty
    assert sections["near_buy"].empty
    assert simple_pick_table(prepare_daily_candidates(rows), "USA").empty
