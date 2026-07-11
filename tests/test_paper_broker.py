from datetime import datetime, timedelta

import pandas as pd
import pytest

from approval_queue import approve_proposal, load_approval_queue, ready_for_paper_broker, sync_approval_queue
from paper_broker import (
    CASH_LEDGER_COLUMNS,
    EXECUTION_HISTORY_COLUMNS,
    FILL_COLUMNS,
    ORDER_COLUMNS,
    PAPER_CASH_LEDGER_FILE,
    PAPER_EXECUTION_HISTORY_FILE,
    PAPER_FILLS_FILE,
    PAPER_ORDERS_FILE,
    PAPER_TRADES_FILE,
    PaperBrokerConfig,
    execute_approved_batch,
    execute_approved_proposal,
    execute_paper_order,
    load_csv,
    submit_paper_order,
)
from paper_portfolio import load_paper_account, load_paper_portfolio, save_paper_portfolio


def approved_proposal(**updates):
    row = {
        "ProposalId": "RM-SET-BUYOK-BUY-20260711",
        "Symbol": "BUYOK",
        "Market": "SET",
        "Action": "BUY",
        "Status": "APPROVED",
        "RiskApproved": True,
        "ApprovalRequired": True,
        "Quantity": 1000,
        "EntryPrice": 10,
        "StopPrice": 9,
        "TargetPrice": 13,
        "ProposedOrderValue": 10000,
        "EstimatedCommission": 15.7,
        "EstimatedSlippage": 10,
        "EstimatedTotalCost": 10025.7,
        "ExpireTime": (datetime.now() + timedelta(days=1)).isoformat(timespec="seconds"),
        "ApprovedTime": datetime.now().isoformat(timespec="seconds"),
        "ApprovedBy": "tester",
        "AIConfidence": 88,
        "RiskScore": 28,
        "ProposalPriority": 2,
    }
    row.update(updates)
    return row


def open_position(symbol="BUYOK", qty=1000, avg=10, last=10, market="SET"):
    return pd.DataFrame(
        [
            {
                "Symbol": symbol,
                "Market": market,
                "PositionQty": qty,
                "AverageCost": avg,
                "LastPrice": last,
                "MarketValue": qty * last,
                "CostBasis": qty * avg,
                "UnrealizedPnL": 0,
                "UnrealizedReturnPct": 0,
                "RealizedPnL": 0,
                "TotalCommission": 0,
                "StopPrice": 9,
                "TargetPrice": 13,
                "LastProposalId": "",
                "LastOrderId": "",
                "LastFillId": "",
                "PositionStatus": "OPEN",
                "OpenedTime": "2026-07-11T09:00:00",
                "UpdatedTime": "2026-07-11T09:00:00",
                "ClosedTime": "",
            }
        ]
    )


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_approved_buy_executes_successfully():
    result = execute_approved_proposal(approved_proposal(), config={"auto_mark_executed": False})

    assert result["fill"]["FillStatus"] == "FILLED"
    assert result["order"]["OrderStatus"] == "FILLED"
    assert result["fill"]["FilledQty"] == 1000


def test_pending_approval_cannot_execute():
    result = execute_approved_proposal(approved_proposal(Status="PENDING_APPROVAL"), config={"auto_mark_executed": False})

    assert result["fill"]["FillStatus"] == "REJECTED"
    assert result["fill"]["RejectReason"] == "NOT_APPROVED"


def test_rejected_proposal_cannot_execute():
    result = execute_approved_proposal(approved_proposal(Status="REJECTED"), config={"auto_mark_executed": False})

    assert result["fill"]["RejectReason"] == "NOT_APPROVED"


def test_expired_proposal_cannot_execute():
    result = execute_approved_proposal(
        approved_proposal(ExpireTime=(datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")),
        config={"auto_mark_executed": False},
    )

    assert result["fill"]["RejectReason"] == "EXPIRED_PROPOSAL"


def test_duplicate_proposal_execution_is_blocked():
    proposal = approved_proposal()
    execute_approved_proposal(proposal, config={"auto_mark_executed": False})
    second = execute_approved_proposal(proposal, config={"auto_mark_executed": False})

    assert second["fill"]["RejectReason"] == "DUPLICATE_EXECUTION"


def test_missing_price_is_rejected():
    result = execute_approved_proposal(approved_proposal(EntryPrice=0, Price=0, Close=0), config={"auto_mark_executed": False})

    assert result["fill"]["RejectReason"] == "MISSING_PRICE"


def test_invalid_quantity_is_rejected():
    result = execute_approved_proposal(approved_proposal(Quantity=0), config={"auto_mark_executed": False})

    assert result["fill"]["RejectReason"] == "INVALID_QUANTITY"


def test_buy_reduces_cash_correctly():
    result = execute_approved_proposal(approved_proposal(), config={"auto_mark_executed": False})

    assert round(result["account"]["Cash"], 2) == 89974.28


def test_buy_creates_new_position():
    result = execute_approved_proposal(approved_proposal(), config={"auto_mark_executed": False})
    portfolio = result["portfolio"]

    assert portfolio.iloc[0]["Symbol"] == "BUYOK"
    assert portfolio.iloc[0]["PositionQty"] == 1000
    assert portfolio.iloc[0]["PositionStatus"] == "OPEN"


def test_add_updates_weighted_average_cost():
    portfolio = open_position(qty=1000, avg=10, last=10)
    proposal = approved_proposal(ProposalId="RM-SET-BUYOK-ADD-20260711", Action="ADD", Quantity=1000, EntryPrice=12)
    result = execute_approved_proposal(proposal, portfolio=portfolio, config={"auto_mark_executed": False})

    assert result["fill"]["FillStatus"] == "FILLED"
    avg = result["portfolio"].iloc[0]["AverageCost"]
    assert avg > 11
    assert avg < 11.1


def test_add_without_position_is_rejected():
    proposal = approved_proposal(ProposalId="RM-SET-BUYOK-ADD-20260711", Action="ADD")
    result = execute_approved_proposal(proposal, config={"auto_mark_executed": False})

    assert result["fill"]["RejectReason"] == "INSUFFICIENT_POSITION"


def test_reduce_lowers_position_quantity_and_realized_pnl():
    portfolio = open_position(qty=1000, avg=9, last=10)
    proposal = approved_proposal(ProposalId="RM-SET-BUYOK-REDUCE-20260711", Action="REDUCE", Quantity=500, EntryPrice=10)
    result = execute_approved_proposal(proposal, portfolio=portfolio, config={"auto_mark_executed": False})

    row = result["portfolio"].iloc[0]
    assert row["PositionQty"] == 500
    assert result["trade"]["RealizedPnL"] > 0


def test_exit_closes_full_position_and_supports_set_odd_lot():
    portfolio = open_position(qty=123, avg=9, last=10)
    proposal = approved_proposal(ProposalId="RM-SET-BUYOK-EXIT-20260711", Action="EXIT", Quantity=100, EntryPrice=10)
    result = execute_approved_proposal(proposal, portfolio=portfolio, config={"auto_mark_executed": False})

    row = result["portfolio"].iloc[0]
    assert result["fill"]["FilledQty"] == 123
    assert row["PositionQty"] == 0
    assert row["PositionStatus"] == "CLOSED"


def test_sell_without_position_is_rejected_and_short_selling_blocked():
    proposal = approved_proposal(ProposalId="RM-SET-BUYOK-REDUCE-20260711", Action="REDUCE", Quantity=100)
    result = execute_approved_proposal(proposal, config={"auto_mark_executed": False})

    assert result["fill"]["RejectReason"] == "INSUFFICIENT_POSITION"


def test_insufficient_cash_rejects_buy():
    result = execute_approved_proposal(
        approved_proposal(),
        account={"InitialCash": 1000, "Cash": 1000},
        config={"auto_mark_executed": False, "initial_cash": 1000},
    )

    assert result["fill"]["RejectReason"] == "INSUFFICIENT_CASH"


def test_commission_calculation_is_correct():
    result = execute_approved_proposal(approved_proposal(), config={"auto_mark_executed": False})

    assert round(result["fill"]["Commission"], 2) == 15.72


def test_buy_slippage_increases_fill_price_and_not_double_counted():
    result = execute_approved_proposal(approved_proposal(), config={"auto_mark_executed": False})

    assert result["fill"]["FillPrice"] == 10.01
    assert round(result["fill"]["NetCashFlow"], 2) == round(-(result["fill"]["GrossValue"] + result["fill"]["Commission"]), 2)


def test_sell_slippage_decreases_fill_price():
    portfolio = open_position(qty=1000, avg=9, last=10)
    proposal = approved_proposal(ProposalId="RM-SET-BUYOK-REDUCE-20260711", Action="REDUCE", Quantity=500, EntryPrice=10)
    result = execute_approved_proposal(proposal, portfolio=portfolio, config={"auto_mark_executed": False})

    assert result["fill"]["FillPrice"] == 9.99


def test_set_quantity_respects_board_lot():
    result = execute_approved_proposal(approved_proposal(Quantity=1050), config={"auto_mark_executed": False})

    assert result["fill"]["FilledQty"] == 1000


def test_usa_integer_quantity_when_fractional_disabled():
    proposal = approved_proposal(Symbol="AAPL", Market="USA", Quantity=10.7, EntryPrice=100, ProposalId="RM-USA-AAPL-BUY-20260711")
    result = execute_approved_proposal(proposal, config={"auto_mark_executed": False})

    assert result["fill"]["FilledQty"] == 10


def test_usa_fractional_quantity_when_enabled():
    proposal = approved_proposal(Symbol="AAPL", Market="USA", Quantity=10.12345, EntryPrice=100, ProposalId="RM-USA-AAPL-BUY-20260711")
    result = execute_approved_proposal(proposal, config={"auto_mark_executed": False, "allow_fractional_usa": True})

    assert result["fill"]["FilledQty"] == 10.1235


def test_partial_fill_policy_fills_configured_percentage_and_rounds():
    result = execute_approved_proposal(
        approved_proposal(Quantity=1050),
        config={"auto_mark_executed": False, "fill_policy": "PARTIAL_FILL", "allow_partial_fill": True, "partial_fill_pct": 50},
    )

    assert result["fill"]["FillStatus"] == "PARTIALLY_FILLED"
    assert result["fill"]["FilledQty"] == 500


def test_trade_cash_and_execution_history_rows_are_created():
    execute_approved_proposal(approved_proposal(), config={"auto_mark_executed": False})

    assert len(load_csv(PAPER_ORDERS_FILE, ORDER_COLUMNS)) == 1
    assert len(load_csv(PAPER_FILLS_FILE, FILL_COLUMNS)) == 1
    assert len(load_csv(PAPER_TRADES_FILE, [])) == 1
    assert len(load_csv(PAPER_CASH_LEDGER_FILE, CASH_LEDGER_COLUMNS)) == 1
    assert len(load_csv(PAPER_EXECUTION_HISTORY_FILE, EXECUTION_HISTORY_COLUMNS)) == 1


def test_execution_history_rejected_row_is_created():
    execute_approved_proposal(approved_proposal(EntryPrice=0), config={"auto_mark_executed": False})

    history = load_csv(PAPER_EXECUTION_HISTORY_FILE, EXECUTION_HISTORY_COLUMNS)
    assert history.iloc[0]["ExecutionStatus"] == "REJECTED"


def test_approval_queue_changes_approved_to_executed_and_ready_list_excludes_it():
    risk = approved_proposal(Status="", ProposalStatus="PENDING_APPROVAL", ProposalAction="BUY", ProposedQty=1000, RiskApproved=True)
    queue, _ = sync_approval_queue(pd.DataFrame([risk]))
    approve_proposal(queue.iloc[0]["ProposalId"])
    ready = ready_for_paper_broker(load_approval_queue())
    assert len(ready) == 1

    execute_approved_proposal(ready.iloc[0].to_dict())
    queue = load_approval_queue()

    assert queue.iloc[0]["Status"] == "EXECUTED"
    assert ready_for_paper_broker(queue).empty


def test_executed_proposal_cannot_be_cancelled():
    risk = approved_proposal(Status="", ProposalStatus="PENDING_APPROVAL", ProposalAction="BUY", ProposedQty=1000, RiskApproved=True)
    queue, _ = sync_approval_queue(pd.DataFrame([risk]))
    approve_proposal(queue.iloc[0]["ProposalId"])
    execute_approved_proposal(ready_for_paper_broker(load_approval_queue()).iloc[0].to_dict())

    from approval_queue import ApprovalQueueError, cancel_proposal

    with pytest.raises(ApprovalQueueError):
        cancel_proposal(risk["ProposalId"])


def test_ids_are_deterministic():
    proposal = approved_proposal()
    first = submit_paper_order(proposal)
    second = submit_paper_order(proposal)
    assert first["PaperOrderId"] == second["PaperOrderId"]
    fill_a = execute_paper_order(first, account=load_paper_account(), portfolio=load_paper_portfolio())
    fill_b = execute_paper_order(first, account=load_paper_account(), portfolio=load_paper_portfolio())
    assert fill_a["FillId"] == fill_b["FillId"]


def test_input_proposal_is_not_modified():
    proposal = approved_proposal()
    original = dict(proposal)
    execute_approved_proposal(proposal, config={"auto_mark_executed": False})
    assert proposal == original


def test_empty_batch_returns_valid_empty_outputs():
    orders, fills, trades, portfolio, account, summary = execute_approved_batch(pd.DataFrame())

    assert orders.empty
    assert fills.empty
    assert trades.empty
    assert summary["Total"] == 0


def test_batch_executes_exit_before_buy_at_same_priority_and_uses_updated_cash():
    portfolio = open_position(symbol="OLD", qty=1000, avg=9, last=10)
    account = {"InitialCash": 1000, "Cash": 1000}
    proposals = pd.DataFrame(
        [
            approved_proposal(ProposalId="RM-SET-NEW-BUY-20260711", Symbol="NEW", Action="BUY", Quantity=1000, EntryPrice=10, ProposalPriority=1),
            approved_proposal(ProposalId="RM-SET-OLD-EXIT-20260711", Symbol="OLD", Action="EXIT", Quantity=1000, EntryPrice=10, ProposalPriority=1),
        ]
    )
    orders, fills, trades, updated_portfolio, updated_account, summary = execute_approved_batch(
        proposals,
        account=account,
        portfolio_dataframe=portfolio,
        config={"auto_mark_executed": False, "initial_cash": 1000},
    )

    assert fills.iloc[0]["Action"] == "EXIT"
    assert "FILLED" in set(fills["FillStatus"])
    assert summary["Total"] == 2


def test_batch_continues_after_normal_rejection():
    proposals = pd.DataFrame(
        [
            approved_proposal(ProposalId="RM-SET-BAD-BUY-20260711", Symbol="BAD", EntryPrice=0),
            approved_proposal(ProposalId="RM-SET-GOOD-BUY-20260711", Symbol="GOOD"),
        ]
    )
    _, fills, _, _, _, summary = execute_approved_batch(proposals, config={"auto_mark_executed": False})

    assert len(fills) == 2
    assert summary["Rejected"] == 1
    assert summary["Filled"] == 1


def test_risk_rejected_proposal_never_enters_paper_broker():
    result = execute_approved_proposal(approved_proposal(Status="REJECTED", RiskApproved=False), config={"auto_mark_executed": False})

    assert result["fill"]["FillStatus"] == "REJECTED"
    assert result["fill"]["RejectReason"] in {"NOT_APPROVED", "RISK_NOT_APPROVED"}
