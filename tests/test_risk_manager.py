import pandas as pd

from risk_manager import (
    PROPOSAL_COLUMNS,
    build_order_proposals,
    build_risk_summary,
    evaluate_risk,
)


def buy_row(**updates):
    row = {
        "Symbol": "AOT",
        "Market": "USA",
        "AIDecision": "BUY",
        "AIConfidence": 85,
        "AIReviewPriority": 1,
        "AIRiskLevel": "LOW",
        "AIBlockers": "",
        "Price": 100,
        "Stop": 95,
        "Target": 115,
        "RiskPct": 5,
        "RR": 3,
        "PriorityScore": 90,
        "OpportunityScore": 80,
        "StrategyScore": 75,
        "LifecycleState": "EARLY",
    }
    row.update(updates)
    return row


def position(qty=100, current_value=10000, average_cost=90):
    return {
        "has_position": True,
        "qty": qty,
        "current_value": current_value,
        "average_cost": average_cost,
    }


def test_strong_buy_with_valid_stop_and_rr_returns_pending_approval():
    result = evaluate_risk(buy_row())

    assert result["ProposalAction"] == "BUY"
    assert result["ProposalStatus"] == "PENDING_APPROVAL"
    assert result["RiskApproved"] is True
    assert result["ApprovalRequired"] is True


def test_buy_with_missing_price_is_rejected():
    result = evaluate_risk(buy_row(Price=0, Entry=0, Close=0))

    assert result["ProposalStatus"] == "REJECTED"
    assert result["RejectReason"] == "MISSING_PRICE"


def test_buy_with_invalid_stop_above_entry_is_rejected():
    result = evaluate_risk(buy_row(Stop=101))

    assert result["ProposalStatus"] == "REJECTED"
    assert result["RejectReason"] == "INVALID_STOP"


def test_buy_with_stop_too_wide_is_rejected():
    result = evaluate_risk(buy_row(Stop=80))

    assert result["ProposalStatus"] == "REJECTED"
    assert result["RejectReason"] == "STOP_TOO_WIDE"


def test_buy_with_rr_below_minimum_is_rejected():
    result = evaluate_risk(buy_row(Target=106))

    assert result["ProposalStatus"] == "REJECTED"
    assert result["RejectReason"] == "LOW_RR"


def test_buy_when_already_owned_is_rejected():
    result = evaluate_risk(buy_row(), portfolio=position())

    assert result["ProposalStatus"] == "REJECTED"
    assert result["RejectReason"] == "ALREADY_OWNED"


def test_add_with_existing_position_returns_valid_proposal():
    result = evaluate_risk(
        buy_row(AIDecision="ADD"),
        portfolio=position(qty=50, current_value=5000),
    )

    assert result["ProposalAction"] == "ADD"
    assert result["ProposalStatus"] == "PENDING_APPROVAL"
    assert result["RiskApproved"] is True


def test_add_with_portfolio_dataframe_shares_column_returns_valid_proposal():
    df = pd.DataFrame([buy_row(Symbol="ADDOK", Market="SET", AIDecision="ADD", Price=20, Stop=19, Target=24)])
    portfolio = pd.DataFrame(
        [
            {
                "Symbol": "ADDOK",
                "Market": "SET",
                "Status": "OPEN",
                "Shares": 250,
                "EntryPrice": 18,
                "CurrentPrice": 20,
                "CurrentValue": 5000,
            }
        ]
    )

    result = build_order_proposals(df, portfolio_dataframe=portfolio)
    row = result.iloc[0]

    assert row["ProposalAction"] == "ADD"
    assert row["ProposalStatus"] == "PENDING_APPROVAL"
    assert bool(row["RiskApproved"]) is True
    assert row["CurrentPositionQty"] == 250


def test_add_without_existing_position_is_rejected():
    result = evaluate_risk(buy_row(AIDecision="ADD"))

    assert result["ProposalStatus"] == "REJECTED"
    assert result["RejectReason"] == "NO_EXISTING_POSITION"


def test_reduce_calculates_partial_quantity_correctly():
    row = buy_row(AIDecision="REDUCE", AIRiskLevel="LOW")
    result = evaluate_risk(row, portfolio=position(qty=100))

    assert result["ProposalAction"] == "REDUCE"
    assert result["ProposedQty"] == 20
    assert result["FinalPositionQty"] == 80


def test_exit_proposes_full_position_quantity():
    result = evaluate_risk(
        buy_row(AIDecision="EXIT"),
        portfolio=position(qty=123),
    )

    assert result["ProposalAction"] == "EXIT"
    assert result["ProposedQty"] == 123
    assert result["FinalPositionQty"] == 0


def test_exit_below_stop_gets_highest_priority():
    result = evaluate_risk(
        buy_row(AIDecision="EXIT", Price=94, Stop=95, AIBlockers="BELOW_STOP"),
        portfolio=position(qty=100),
    )

    assert result["ProposalPriority"] == 1
    assert result["RiskScore"] >= 90


def test_set_quantity_rounds_down_to_board_lot():
    result = evaluate_risk(
        buy_row(Symbol="AOT.BK", Market="SET", Price=10, Stop=9, Target=12),
        config={"max_order_value": 12345},
    )

    assert result["RiskApproved"] is True
    assert result["ProposedQty"] % 100 == 0


def test_usa_quantity_rounds_down_to_integer():
    result = evaluate_risk(buy_row(Price=100, Stop=90, Target=120))

    assert result["RiskApproved"] is True
    assert float(result["ProposedQty"]).is_integer()


def test_insufficient_cash_reduces_quantity():
    result = evaluate_risk(
        buy_row(Price=100, Stop=90, Target=120),
        account={"AvailableCash": 2500},
    )

    assert result["RiskApproved"] is True
    assert result["ProposedOrderValue"] <= 2500
    assert result["ProposedQty"] < 100


def test_order_below_minimum_value_is_rejected():
    result = evaluate_risk(
        buy_row(Price=10, Stop=9, Target=12),
        account={"AvailableCash": 900},
    )

    assert result["ProposalStatus"] == "REJECTED"
    assert result["RejectReason"] == "BELOW_MIN_ORDER"


def test_maximum_position_cap_is_respected():
    result = evaluate_risk(
        buy_row(Price=100, Stop=95, Target=115),
        config={"max_position_pct": 5},
    )

    assert result["RiskApproved"] is True
    assert result["ProposedOrderValue"] <= 5000


def test_maximum_total_exposure_is_respected():
    result = evaluate_risk(
        buy_row(),
        account={"TotalExposure": 80000},
    )

    assert result["ProposalStatus"] == "REJECTED"
    assert result["RejectReason"] == "MAX_TOTAL_EXPOSURE"


def test_maximum_open_positions_blocks_new_buy():
    result = evaluate_risk(
        buy_row(),
        account={"OpenPositions": 10},
    )

    assert result["ProposalStatus"] == "REJECTED"
    assert result["RejectReason"] == "MAX_OPEN_POSITIONS"


def test_ai_severe_blocker_rejects_buy():
    result = evaluate_risk(buy_row(AIBlockers="EXTENDED"))

    assert result["ProposalStatus"] == "REJECTED"
    assert result["RejectReason"] == "AI_BLOCKED"


def test_exit_is_not_blocked_by_low_rr_or_extended():
    result = evaluate_risk(
        buy_row(AIDecision="EXIT", AIBlockers="LOW_RR; EXTENDED", RR=0.5),
        portfolio=position(qty=100),
    )

    assert result["ProposalAction"] == "EXIT"
    assert result["RiskApproved"] is True


def test_commission_and_slippage_calculations_are_correct():
    result = evaluate_risk(buy_row())

    assert result["ProposedOrderValue"] == 15000
    assert round(result["EstimatedCommission"], 2) == 23.55
    assert round(result["EstimatedSlippage"], 2) == 15.00


def test_cash_after_order_calculation_is_correct():
    result = evaluate_risk(buy_row())

    assert round(result["CashAfterOrder"], 2) == 84961.45


def test_risk_score_remains_within_zero_to_one_hundred():
    rows = [
        buy_row(),
        buy_row(AIDecision="EXIT", AIBlockers="BELOW_STOP", Price=94, Stop=95),
        buy_row(AIBlockers="EXTENDED"),
    ]

    for row in rows:
        result = evaluate_risk(row, portfolio=position() if row["AIDecision"] == "EXIT" else None)
        assert 0 <= result["RiskScore"] <= 100


def test_high_risk_buy_is_rejected():
    result = evaluate_risk(buy_row(AIRiskLevel="HIGH"))

    assert result["ProposalStatus"] == "REJECTED"
    assert result["RejectReason"] == "HIGH_RISK"


def test_non_actionable_ai_decision_returns_no_proposal():
    result = evaluate_risk(buy_row(AIDecision="WATCH"))

    assert result["ProposalStatus"] == "NO_PROPOSAL"
    assert result["ProposalAction"] == "NONE"
    assert result["RiskApproved"] is False


def test_input_dataframe_is_not_modified():
    df = pd.DataFrame([buy_row()])
    original = df.copy(deep=True)

    build_order_proposals(df)

    pd.testing.assert_frame_equal(df, original)


def test_empty_dataframe_returns_expected_columns():
    result = build_order_proposals(pd.DataFrame())

    assert result.empty
    for column in PROPOSAL_COLUMNS:
        assert column in result.columns


def test_batch_sorting_is_correct():
    df = pd.DataFrame(
        [
            buy_row(Symbol="WATCH", AIDecision="WATCH", AIConfidence=20),
            buy_row(Symbol="BUY", AIConfidence=80),
            buy_row(Symbol="EXIT", AIDecision="EXIT", AIBlockers="BELOW_STOP", Price=94, Stop=95),
        ]
    )
    portfolio = pd.DataFrame(
        [
            {"Symbol": "EXIT", "Market": "USA", "Status": "OPEN", "Shares": 10, "CurrentPrice": 94, "CurrentValue": 940},
        ]
    )
    result = build_order_proposals(df, portfolio_dataframe=portfolio)

    assert result.iloc[0]["Symbol"] == "EXIT"
    assert result.iloc[0]["ProposalPriority"] == 1


def test_risk_summary_totals_are_correct():
    proposals = build_order_proposals(pd.DataFrame([buy_row(), buy_row(Symbol="WATCH", AIDecision="WATCH")]))
    summary = build_risk_summary(proposals)
    row = summary.iloc[0]

    assert row["PendingProposals"] == 1
    assert row["BuyProposals"] == 1
    assert row["TotalProposedBuyValue"] == 15000


def test_require_manual_approval_false_returns_approved_for_paper_without_execution():
    result = evaluate_risk(
        buy_row(),
        config={"require_manual_approval": False},
    )

    assert result["RiskApproved"] is True
    assert result["ProposalStatus"] == "APPROVED_FOR_PAPER"
    assert result["ApprovalRequired"] is True
