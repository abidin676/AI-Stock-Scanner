import pandas as pd

from ai_decision_engine import AI_COLUMNS, build_ai_decisions, make_ai_decision


def strong_buy_row():
    return {
        "Symbol": "TEST",
        "Market": "USA",
        "StrategySignal": "BUY",
        "StrategyScore": 88,
        "Signal": "BUY",
        "LifecycleState": "EARLY",
        "OpportunityScore": 82,
        "RecommendedAction": "Buy",
        "PriorityScore": 91,
        "PriorityAction": "Review First",
        "MarketQualityScore": 72,
        "MarketQualityLabel": "Healthy",
        "Price": 100,
        "Stop": 95,
        "RiskPct": 4,
        "RR": 3,
        "PatternScore": 80,
        "FreshnessScore": 84,
    }


def test_strong_early_opportunity_returns_buy():
    result = make_ai_decision(strong_buy_row())

    assert result["AIDecision"] == "BUY"
    assert result["AIAction"] == "Enter New Position"
    assert result["AIRequiresApproval"] is True


def test_good_seed_weak_market_returns_prepare():
    row = strong_buy_row()
    row.update(
        {
            "LifecycleState": "SEED",
            "RecommendedAction": "Watch",
            "StrategySignal": "SEED WATCH",
            "MarketQualityScore": 10,
            "MarketQualityLabel": "Avoid",
        }
    )

    result = make_ai_decision(row)

    assert result["AIDecision"] == "PREPARE"
    assert "MARKET_AVOID" in result["AIBlockers"]


def test_moderate_setup_returns_watch():
    row = {
        "Symbol": "MID",
        "Market": "USA",
        "StrategySignal": "WATCH",
        "LifecycleState": "EARLY",
        "OpportunityScore": 45,
        "RecommendedAction": "Watch",
        "PriorityScore": 50,
        "MarketQualityScore": 55,
        "Price": 20,
        "RiskPct": 4,
        "RR": 2,
    }

    result = make_ai_decision(row)

    assert result["AIDecision"] == "WATCH"


def test_extended_stock_returns_avoid():
    row = strong_buy_row()
    row.update(
        {
            "LifecycleState": "EXTENDED",
            "StrategySignal": "EXTENDED",
        }
    )

    result = make_ai_decision(row)

    assert result["AIDecision"] == "AVOID"
    assert "EXTENDED" in result["AIBlockers"]


def test_low_rr_is_blocked():
    row = strong_buy_row()
    row["RR"] = 1.2

    result = make_ai_decision(row)

    assert result["AIDecision"] == "AVOID"
    assert "LOW_RR" in result["AIBlockers"]


def test_existing_healthy_position_returns_hold():
    row = {
        "Symbol": "HOLDME",
        "Market": "USA",
        "StrategySignal": "WATCH",
        "LifecycleState": "EARLY",
        "OpportunityScore": 62,
        "PriorityScore": 70,
        "MarketQualityScore": 55,
        "Price": 50,
        "RiskPct": 4,
        "RR": 2.2,
    }
    portfolio = {
        "has_position": True,
        "qty": 10,
        "average_cost": 48,
        "current_price": 50,
        "stop_price": 45,
        "unrealized_return_pct": 4.1,
    }

    result = make_ai_decision(row, portfolio=portfolio)

    assert result["AIDecision"] == "HOLD"


def test_existing_position_below_stop_returns_exit():
    row = {
        "Symbol": "STOP",
        "Market": "USA",
        "StrategySignal": "WATCH",
        "LifecycleState": "EARLY",
        "PriorityScore": 60,
        "OpportunityScore": 50,
        "Price": 44,
        "RiskPct": 4,
        "RR": 2,
    }
    portfolio = {
        "has_position": True,
        "qty": 10,
        "current_price": 44,
        "stop_price": 45,
    }

    result = make_ai_decision(row, portfolio=portfolio)

    assert result["AIDecision"] == "EXIT"
    assert result["AIRequiresApproval"] is True


def test_existing_position_does_not_return_buy():
    result = make_ai_decision(
        strong_buy_row(),
        portfolio={
            "has_position": True,
            "qty": 10,
            "current_price": 100,
            "stop_price": 90,
            "unrealized_return_pct": 5,
        },
    )

    assert result["AIDecision"] != "BUY"
    assert result["AIPositionIntent"] in {"ADD", "HOLD", "REDUCE", "CLOSE"}


def test_missing_optional_columns_does_not_crash():
    result = make_ai_decision({"Symbol": "MIN", "Market": "SET"})

    assert result["Symbol"] == "MIN"
    assert result["AIDecision"] in {
        "AVOID",
        "NO_ACTION",
        "WATCH",
    }


def test_input_dataframe_is_not_modified():
    df = pd.DataFrame([strong_buy_row()])
    original = df.copy(deep=True)

    build_ai_decisions(df)

    pd.testing.assert_frame_equal(df, original)


def test_confidence_remains_within_zero_to_one_hundred():
    rows = [
        strong_buy_row(),
        {"Symbol": "BAD", "Market": "USA", "Price": 1, "RR": 0.1, "RiskPct": 50},
        {"Symbol": "EMPTY", "Market": "SET"},
    ]

    for row in rows:
        result = make_ai_decision(row)
        assert 0 <= result["AIConfidence"] <= 100


def test_batch_output_sorting_is_correct():
    watch = {
        "Symbol": "WATCH",
        "Market": "USA",
        "Price": 10,
        "PriorityScore": 50,
        "OpportunityScore": 45,
        "StrategySignal": "WATCH",
        "RecommendedAction": "Watch",
        "PriorityRank": 1,
    }
    buy = strong_buy_row()
    buy["Symbol"] = "BUYME"
    buy["PriorityRank"] = 5
    df = pd.DataFrame([watch, buy])

    output = build_ai_decisions(df)

    assert output.iloc[0]["Symbol"] == "BUYME"
    assert output.iloc[0]["AIReviewPriority"] <= output.iloc[1]["AIReviewPriority"]


def test_ai_requires_approval_for_actionable_decisions():
    buy = make_ai_decision(strong_buy_row())
    exit_decision = make_ai_decision(
        {
            "Symbol": "STOP",
            "Market": "USA",
            "Price": 44,
            "PriorityScore": 50,
            "OpportunityScore": 40,
        },
        portfolio={
            "has_position": True,
            "qty": 10,
            "current_price": 44,
            "stop_price": 45,
        },
    )
    watch = make_ai_decision(
        {
            "Symbol": "WATCH",
            "Market": "USA",
            "Price": 10,
            "PriorityScore": 50,
            "OpportunityScore": 45,
            "RecommendedAction": "Watch",
        }
    )

    assert buy["AIRequiresApproval"] is True
    assert exit_decision["AIRequiresApproval"] is True
    assert watch["AIRequiresApproval"] is False


def test_empty_dataframe_returns_expected_ai_columns():
    df = pd.DataFrame()

    output = build_ai_decisions(df)

    assert output.empty
    for column in AI_COLUMNS:
        assert column in output.columns
