import pandas as pd
import pytest

from alert_engine import valid_seed_candidates
from candidate_eligibility import split_candidate_queues
from fresh_cross_candidates import (
    fresh_cross_candidates,
    rank_candidate_universe,
    save_candidate_ranking_outputs,
    top_five_candidates,
)
from priority_engine import ensure_priority_inputs
from views.scanner import (
    all_fresh_cross_table,
    build_simple_dashboard_sections,
    prepare_daily_candidates,
    simple_pick_table,
)


def candidate(symbol, market="SET", score=80, cross_age=0, **overrides):
    row = {
        "Symbol": symbol,
        "Market": market,
        "EMA9": 11,
        "EMA20": 10,
        "EMA50": 9.5,
        "PreviousEMA9": 9.8 if cross_age == 0 else 10.5,
        "PreviousEMA20": 10,
        "BullishCrossEvent": cross_age == 0,
        "DaysSinceEMA9CrossEMA20": cross_age,
        "LatestPriceDate": "2026-07-16",
        "CrossDate": "2026-07-16" if cross_age == 0 else "2026-07-15",
        "CrossAgeSource": "days_since_bullish_ema_cross",
        "LifecycleState": "SEED",
        "StrategySignal": "SEED WATCH",
        "StrategySetup": "Early Reversal",
        "RecommendedAction": "Watch Closely",
        "AIDecision": "PREPARE",
        "AIConfidence": score,
        "PriorityScore": score,
        "StrategyScore": score,
        "ExpansionScore": 10,
        "DistanceEMA20Pct": 2,
        "Price": 11,
        "RVOL": 1.5,
        "RSI": 55,
        "EMA20Improving": True,
        "SeedScore": 80,
        "OpportunityScore": 70,
        "RR": 2,
        "EntryPrice": 11,
        "StopPrice": 10,
        "TargetPrice": 13,
        "RiskApproved": True,
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize("market", ["SET", "USA"])
def test_all_eligible_eight_are_visible_and_top_five_are_highest_scores(market):
    rows = pd.DataFrame(
        [
            candidate(f"{market}{index}", market=market, score=50 + index)
            for index in range(8)
        ]
    )
    prepared = prepare_daily_candidates(rows)

    all_fresh = all_fresh_cross_table(prepared, market)
    top_five = simple_pick_table(prepared, market)

    assert len(all_fresh) == 8
    assert len(top_five) == 5
    assert top_five["Symbol"].tolist() == [
        f"{market}{index}"
        for index in [7, 6, 5, 4, 3]
    ]
    assert set(top_five["Symbol"]).issubset(set(all_fresh["Symbol"]))


def test_old_cross_is_excluded_from_all_fresh_and_top_five():
    rows = pd.DataFrame(
        [
            candidate("FRESH", score=80),
            candidate(
                "OLD",
                score=999,
                cross_age=5,
                CrossDate="2026-07-09",
            ),
        ]
    )

    fresh = fresh_cross_candidates(rows)
    top = top_five_candidates(rows, "SET")

    assert fresh["Symbol"].tolist() == ["FRESH"]
    assert top["Symbol"].tolist() == ["FRESH"]


def test_high_expansion_is_extended_even_when_legacy_lifecycle_says_watch():
    rows = pd.DataFrame(
        [
            candidate(
                "EXPANDED",
                score=999,
                LifecycleState="WATCH",
                ExpansionScore=100,
            )
        ]
    )

    _, audit, fresh = rank_candidate_universe(rows)
    _, _, watch_queue = split_candidate_queues(rows)
    alerts = valid_seed_candidates(rows)
    sections = build_simple_dashboard_sections(rows)

    assert fresh.empty
    assert not bool(audit.iloc[0]["FreshCrossEligible"])
    assert audit.iloc[0]["ExclusionReason"] == "EXTENDED"
    assert top_five_candidates(rows, "SET").empty
    assert watch_queue.empty
    assert alerts.empty
    assert sections["watch"].empty


def test_low_score_eligible_remains_in_all_fresh_with_ranked_below_reason():
    rows = pd.DataFrame(
        [candidate(f"S{index}", score=100 - index) for index in range(8)]
    )

    _, audit, fresh = rank_candidate_universe(rows)
    low = audit[audit["Symbol"] == "S7"].iloc[0]

    assert len(fresh) == 8
    assert bool(low["FreshCrossEligible"])
    assert not bool(low["IncludedInTop5"])
    assert low["ExclusionReason"] == "RANKED_BELOW_TOP5"


def test_ranking_is_deterministic_for_equal_scores():
    rows = pd.DataFrame(
        [
            candidate("ZZZ", score=80),
            candidate("AAA", score=80),
            candidate("MMM", score=80),
        ]
    )

    ranked = fresh_cross_candidates(rows)

    assert ranked["Symbol"].tolist() == ["AAA", "MMM", "ZZZ"]


def test_mo_old_cross_fixture_never_reaches_top_five_watch_or_alert(tmp_path):
    mo = candidate(
        "MO",
        market="USA",
        score=999,
        cross_age=16,
        LatestPriceDate="2026-07-16",
        CrossDate="2026-06-24",
        PreviousEMA9=10.8,
        PreviousEMA20=10,
        BullishCrossEvent=False,
    )
    rows = pd.DataFrame([mo])

    _, audit, fresh = rank_candidate_universe(rows)
    audit_row = audit.iloc[0]
    _, _, watch_queue = split_candidate_queues(rows)
    sections = build_simple_dashboard_sections(rows)
    alerts = valid_seed_candidates(rows)

    assert fresh.empty
    assert audit_row["LatestPriceDate"] == "2026-07-16"
    assert audit_row["CrossDate"] == "2026-06-24"
    assert audit_row["CrossAge"] == 16
    assert audit_row["CrossAgeSource"] == "days_since_bullish_ema_cross"
    assert audit_row["FreshCrossStatus"] == "STALE_CROSS"
    assert audit_row["FreshCrossStatusLabel"] == "Cross เก่า"
    assert not bool(audit_row["FreshCrossEligible"])
    assert audit_row["ExclusionReason"] == "CROSS_AGE_16"
    assert top_five_candidates(rows, "USA").empty
    assert watch_queue.empty
    assert sections["watch"].empty
    assert alerts.empty

    candidates_path = tmp_path / "fresh.csv"
    audit_path = tmp_path / "audit.csv"
    save_candidate_ranking_outputs(
        rows,
        candidates_path=candidates_path,
        audit_path=audit_path,
    )
    written = pd.read_csv(audit_path)
    assert written.iloc[0]["Symbol"] == "MO"
    assert written.iloc[0]["ExclusionReason"] == "CROSS_AGE_16"


def test_missing_cross_date_or_authoritative_source_cannot_be_fresh():
    rows = pd.DataFrame(
        [
            candidate("NO_DATE", CrossDate=None),
            candidate("LEGACY", CrossAgeSource="", DaysSinceEMA9CrossEMA20=0),
            candidate("NO_EVENT", BullishCrossEvent=False),
        ]
    )

    _, audit, fresh = rank_candidate_universe(rows)

    assert fresh.empty
    assert set(audit["ExclusionReason"]) == {"NO_CROSS_EVENT"}


def test_priority_normalization_never_turns_missing_cross_age_into_today():
    normalized = ensure_priority_inputs(
        pd.DataFrame(
            [
                candidate(
                    "NO_HISTORY",
                    DaysSinceEMA9CrossEMA20=None,
                    CrossDate=None,
                )
            ]
        )
    )

    assert pd.isna(normalized.iloc[0]["DaysSinceEMA9CrossEMA20"])
