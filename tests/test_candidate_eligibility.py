import pandas as pd
import pytest

from candidate_eligibility import (
    evaluate_candidate_eligibility,
    is_buy_queue_candidate,
    is_watch_queue_candidate,
    split_candidate_queues,
)


def ranked_row(**overrides):
    row = {
        "Symbol": "GOOD.BK",
        "Market": "SET",
        "StrategySignal": "BUY",
        "LifecycleState": "SEED",
        "RecommendedAction": "Review First",
        "AIDecision": "BUY",
        "AIConfidence": 72,
        "EMA9": 11,
        "EMA20": 10,
        "DaysSinceEMA9CrossEMA20": 0,
        "LatestPriceDate": "2026-07-17",
        "CrossDate": "2026-07-17",
        "CrossAgeSource": "days_since_bullish_ema_cross",
        "PreviousEMA9": 9.8,
        "PreviousEMA20": 10,
        "BullishCrossEvent": True,
        "RR": 2.4,
        "EntryPrice": 10,
        "StopPrice": 9,
        "TargetPrice": 13,
        "SeedScore": 86,
        "OpportunityScore": 76,
        "PriorityRank": 1,
        "PriorityScore": 90,
    }
    row.update(overrides)
    return row


def test_aura_like_ignore_skip_avoid_is_not_buy_queue_candidate():
    row = pd.Series(
        ranked_row(
            Symbol="AURA.BK",
            StrategySignal="SKIP",
            LifecycleState="SKIP",
            RecommendedAction="Ignore",
            AIDecision="AVOID",
            AIConfidence=35,
            RR=3.09,
            SeedScore=85.8,
            PriorityScore=58.42,
            PatternName="Wyckoff Accumulation",
        )
    )

    result = evaluate_candidate_eligibility(row)

    assert is_buy_queue_candidate(row) is False
    assert result.queue_class == "IGNORE"
    assert "Scanner/lifecycle SKIP" in result.blocking_reasons
    assert is_watch_queue_candidate(row) is False


def test_strong_actionable_candidate_enters_buy_without_duplicate_ai_buy():
    ranked = pd.DataFrame([ranked_row(AIDecision="WATCH", AIConfidence=50)])

    _, buy_queue, watch_queue = split_candidate_queues(ranked)

    assert buy_queue["Symbol"].tolist() == ["GOOD.BK"]
    assert watch_queue.empty
    assert buy_queue.iloc[0]["QueueClass"] == "BUY"


def test_prepare_decision_does_not_enter_buy_when_confirmation_missing():
    ranked = pd.DataFrame([
        ranked_row(
            Symbol="PREP.BK",
            StrategySignal="WATCH",
            LifecycleState="SEED",
            PriorityScore=60,
            SeedScore=88,
            RR=1.7,
            StopPrice=0,
            TargetPrice=0,
        )
    ])

    _, buy_queue, watch_queue = split_candidate_queues(ranked)

    assert buy_queue.empty
    assert watch_queue["Symbol"].tolist() == ["PREP.BK"]
    assert watch_queue.iloc[0]["QueueClass"] == "PREPARE"


def test_watch_decision_enters_watch_queue_not_buy_queue():
    ranked = pd.DataFrame(
        [
            ranked_row(
                Symbol="WATCH.BK",
                AIDecision="WATCH",
                RecommendedAction="Watch Closely",
                PriorityScore=50,
                SeedScore=65,
                RR=1.6,
            )
        ]
    )

    _, buy_queue, watch_queue = split_candidate_queues(ranked)

    assert buy_queue.empty
    assert watch_queue["Symbol"].tolist() == ["WATCH.BK"]


def test_ai_watch_has_rejection_reason_when_watch_queue_empty():
    ranked = pd.DataFrame(
        [
            ranked_row(
                Symbol="WATCHSKIP.BK",
                AIDecision="WATCH",
                StrategySignal="SKIP",
                LifecycleState="SKIP",
                RecommendedAction="Watch",
                SeedScore=85,
                PriorityScore=60,
                RR=2.0,
            )
        ]
    )

    normalized, buy_queue, watch_queue = split_candidate_queues(ranked)

    assert buy_queue.empty
    assert watch_queue.empty
    assert normalized.iloc[0]["QueueClass"] == "IGNORE"
    assert "Scanner/lifecycle SKIP" in normalized.iloc[0]["BlockingReasons"]


def test_skip_and_extended_are_excluded_from_queues():
    ranked = pd.DataFrame(
        [
            ranked_row(
                Symbol="SKIP.BK",
                StrategySignal="SKIP",
                LifecycleState="SKIP",
                SeedScore=20,
                PriorityScore=20,
            ),
            ranked_row(
                Symbol="EXT.BK",
                StrategySignal="EXTENDED",
                LifecycleState="EXTENDED",
                ExpansionScore=90,
            ),
        ]
    )

    _, buy_queue, watch_queue = split_candidate_queues(ranked)

    assert buy_queue.empty
    assert watch_queue.empty


def test_invalid_price_and_low_rr_remain_blocked():
    invalid_price = evaluate_candidate_eligibility(
        pd.Series(ranked_row(EntryPrice=0))
    )
    low_rr = evaluate_candidate_eligibility(
        pd.Series(ranked_row(RR=1.0))
    )

    assert invalid_price.queue_class == "IGNORE"
    assert "Missing or invalid entry price" in invalid_price.blocking_reasons
    assert low_rr.queue_class == "IGNORE"
    assert any("RR below hard minimum" in reason for reason in low_rr.blocking_reasons)


def test_missing_optional_fields_do_not_crash_and_do_not_enter_buy_queue():
    ranked = pd.DataFrame(
        [
            {
                "Symbol": "MISSING.BK",
                "Market": "SET",
            }
        ]
    )

    normalized, buy_queue, watch_queue = split_candidate_queues(ranked)

    assert len(normalized) == 1
    assert buy_queue.empty
    assert watch_queue.empty
    assert "EligibilityReasons" in normalized.columns


@pytest.mark.parametrize("cross_age", [3, 5, 10])
def test_stale_cross_cannot_enter_buy_prepare_or_watch_queue(cross_age):
    ranked = pd.DataFrame(
        [
            ranked_row(
                Symbol="STALE.BK",
                DaysSinceEMA9CrossEMA20=cross_age,
                AIConfidence=100,
                PriorityScore=100,
                SeedScore=100,
                RR=5,
            )
        ]
    )

    normalized, buy_queue, watch_queue = split_candidate_queues(ranked)

    assert buy_queue.empty
    assert watch_queue.empty
    assert normalized.iloc[0]["QueueClass"] == "IGNORE"
    assert normalized.iloc[0]["FreshCrossStatusLabel"] == "Cross เก่า"
    assert "Fresh EMA cross required" in normalized.iloc[0]["BlockingReasons"]


def test_cross_age_two_can_enter_buy_queue():
    ranked = pd.DataFrame(
        [
            ranked_row(
                Symbol="AGE2.BK",
                DaysSinceEMA9CrossEMA20=2,
            )
        ]
    )

    normalized, buy_queue, _ = split_candidate_queues(ranked)

    assert normalized.iloc[0]["FreshCrossEligible"]
    assert buy_queue["Symbol"].tolist() == ["AGE2.BK"]
