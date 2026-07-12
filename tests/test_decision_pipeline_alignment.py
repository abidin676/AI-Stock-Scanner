import pandas as pd

from priority_engine import apply_priority_mode
from risk_manager import build_order_proposals, build_risk_summary


def pipeline_row(**overrides):
    row = {
        "Symbol": "PIPE.BK",
        "Market": "SET",
        "AIDecision": "BUY",
        "QueueClass": "BUY",
        "EligibleForBuyQueue": True,
        "PriorityScore": 88,
        "OpportunityScore": 80,
        "StrategyScore": 80,
        "LifecycleState": "SEED",
        "StrategySignal": "BUY",
        "EntryPrice": 10,
        "StopPrice": 9,
        "TargetPrice": 13,
        "RR": 3,
        "RiskRewardRatio": 3,
        "AIConfidence": 70,
    }
    row.update(overrides)
    return row


def test_risk_manager_creates_no_proposal_for_prepare_and_watch():
    data = pd.DataFrame(
        [
            pipeline_row(Symbol="PREP.BK", AIDecision="PREPARE", QueueClass="PREPARE", EligibleForBuyQueue=False),
            pipeline_row(Symbol="WATCH.BK", AIDecision="WATCH", QueueClass="WATCH", EligibleForBuyQueue=False),
        ]
    )

    proposals = build_order_proposals(data)

    assert proposals["ProposalStatus"].tolist() == ["NO_PROPOSAL", "NO_PROPOSAL"]
    assert proposals["RejectReason"].tolist() == ["QUEUE_CLASS_PREPARE", "QUEUE_CLASS_WATCH"]
    assert float(proposals["ProposedOrderValue"].sum()) == 0


def test_zero_valid_proposals_produces_zero_projected_exposure():
    proposals = build_order_proposals(
        pd.DataFrame(
            [
                pipeline_row(
                    AIDecision="PREPARE",
                    QueueClass="PREPARE",
                    EligibleForBuyQueue=False,
                )
            ]
        )
    )
    summary = build_risk_summary(
        proposals,
        account={
            "AccountEquity": 100000,
            "AvailableCash": 100000,
            "TotalExposure": 579,
            "OpenPositions": 1,
        },
    )

    row = summary.iloc[0]
    assert row["ProjectedExposure"] == 0
    assert row["ProjectedExposurePct"] == 0
    assert row["CurrentExposure"] == 579


def test_avoid_candidate_not_risk_buy_proposal():
    proposals = build_order_proposals(
        pd.DataFrame(
            [
                pipeline_row(
                    AIDecision="AVOID",
                    QueueClass="IGNORE",
                    EligibleForBuyQueue=False,
                )
            ]
        )
    )

    row = proposals.iloc[0]
    assert row["ProposalStatus"] == "NO_PROPOSAL"
    assert row["ProposalAction"] == "NONE"
    assert bool(row["RiskApproved"]) is False
    assert row["RejectReason"] == "QUEUE_CLASS_IGNORE"


def test_priority_ranking_does_not_mutate_scanner_or_lifecycle_fields():
    data = pd.DataFrame(
        [
            {
                "Symbol": "AAA.BK",
                "Market": "SET",
                "OpportunityScore": 60,
                "LifecycleState": "SKIP",
                "StrategySignal": "SKIP",
                "SeedScore": 85,
                "PriorityScore": 1,
            },
            {
                "Symbol": "BBB.BK",
                "Market": "SET",
                "OpportunityScore": 80,
                "LifecycleState": "SEED",
                "StrategySignal": "SEED WATCH",
                "SeedScore": 90,
                "PriorityScore": 2,
            },
        ]
    )

    prioritized = apply_priority_mode(data, "Seed First")
    by_symbol = prioritized.set_index("Symbol")

    assert by_symbol.loc["AAA.BK", "LifecycleState"] == "SKIP"
    assert by_symbol.loc["AAA.BK", "StrategySignal"] == "SKIP"
    assert by_symbol.loc["BBB.BK", "LifecycleState"] == "SEED"
    assert by_symbol.loc["BBB.BK", "StrategySignal"] == "SEED WATCH"
    assert prioritized["PriorityScore"].between(0, 100).all()
    assert "PriorityBaseScore" in prioritized.columns
    assert "PriorityReason" in prioritized.columns
