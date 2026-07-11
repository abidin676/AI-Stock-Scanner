from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from paper_broker import (
    DAILY_STATE_COLUMNS,
    FILL_COLUMNS,
    ORDER_COLUMNS,
    ORDER_EVENT_COLUMNS,
    PAPER_DAILY_STATE_FILE,
    PAPER_FILLS_FILE,
    PAPER_ORDER_EVENTS_FILE,
    PAPER_ORDERS_FILE,
    cancel_paper_order,
    create_order,
    create_paper_order,
    execute_approved_proposal,
    load_csv,
    save_csv,
    submit_order,
    transition_order_data,
    validate_order_transition,
)
from paper_portfolio import load_paper_account, load_paper_portfolio


def approved_proposal(**updates):
    row = {
        "ProposalId": "RM-SET-BUYOK-BUY-20260711",
        "Symbol": "BUYOK",
        "Market": "SET",
        "Action": "BUY",
        "Status": "APPROVED",
        "RiskApproved": True,
        "Quantity": 1000,
        "EntryPrice": 10,
        "StopPrice": 9,
        "TargetPrice": 13,
        "ProposedOrderValue": 10000,
        "ExpireTime": (datetime.now() + timedelta(days=1)).isoformat(timespec="seconds"),
        "AIConfidence": 88,
        "RiskScore": 28,
        "ProposalPriority": 2,
    }
    row.update(updates)
    return row


def open_position(symbol="BUYOK", qty=1000, avg=10, last=10, market="SET"):
    return {
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


def open_positions(count=5, include_buyok=False):
    rows = []
    for idx in range(count):
        symbol = "BUYOK" if include_buyok and idx == 0 else f"POS{idx}.BK"
        rows.append(open_position(symbol=symbol))
    return pd.DataFrame(rows)


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def seed_daily_loss_state():
    save_csv(
        pd.DataFrame(
            [
                {
                    "TradingDate": datetime.now(UTC).date().isoformat(),
                    "StartOfDayEquity": 100000.0,
                    "CurrentEquity": 100000.0,
                    "DailyPnL": 0.0,
                    "DailyPnLPct": 0.0,
                    "LossLimitTriggered": False,
                    "UpdatedTime": datetime.now(UTC).replace(tzinfo=None).isoformat(timespec="seconds"),
                }
            ]
        ),
        PAPER_DAILY_STATE_FILE,
        DAILY_STATE_COLUMNS,
    )


def test_valid_buy_lifecycle_created_submitted_filled_and_audited():
    result = execute_approved_proposal(approved_proposal(), config={"auto_mark_executed": False})

    assert result["order"]["Status"] == "FILLED"
    events = load_csv(PAPER_ORDER_EVENTS_FILE, ORDER_EVENT_COLUMNS)
    assert events["EventType"].tolist() == ["ORDER_CREATED", "ORDER_SUBMITTED", "ORDER_FILLED"]
    assert events.iloc[-1]["CashBefore"] > events.iloc[-1]["CashAfter"]


def test_valid_exit_lifecycle_created_submitted_filled():
    portfolio = pd.DataFrame([open_position(qty=123, avg=9)])
    proposal = approved_proposal(Action="EXIT", Quantity=100, ProposalId="RM-SET-BUYOK-EXIT-20260711")

    result = execute_approved_proposal(proposal, portfolio=portfolio, config={"auto_mark_executed": False})

    assert result["order"]["Status"] == "FILLED"
    assert result["fill"]["FilledQty"] == 123
    assert result["portfolio"].iloc[0]["PositionStatus"] == "CLOSED"


def test_invalid_transition_rejected():
    order = create_order(approved_proposal())
    order["Status"] = "FILLED"
    order["OrderStatus"] = "FILLED"

    assert not validate_order_transition("FILLED", "SUBMITTED")
    with pytest.raises(ValueError):
        transition_order_data(order, "SUBMITTED")


def test_cancel_created_order_does_not_change_cash_or_position():
    order = create_paper_order(approved_proposal())
    account_before = load_paper_account()
    portfolio_before = load_paper_portfolio()

    cancelled = cancel_paper_order(order["PaperOrderId"], reason="test_cancel")

    assert cancelled["Status"] == "CANCELLED"
    assert load_paper_account()["Cash"] == account_before["Cash"]
    assert load_paper_portfolio().equals(portfolio_before)


def test_cancel_submitted_order_and_reject_cancel_filled():
    created = create_paper_order(approved_proposal(ProposalId="RM-SET-CANCEL-BUY-20260711", Symbol="CANCEL"))
    submitted = submit_order(created)
    save_csv(pd.DataFrame([submitted]), PAPER_ORDERS_FILE, ORDER_COLUMNS)

    assert cancel_paper_order(submitted["PaperOrderId"], reason="cancel_submitted")["Status"] == "CANCELLED"

    filled = execute_approved_proposal(approved_proposal(), config={"auto_mark_executed": False})["order"]
    with pytest.raises(ValueError):
        cancel_paper_order(filled["PaperOrderId"])


def test_duplicate_execution_does_not_change_cash_or_position():
    proposal = approved_proposal()
    first = execute_approved_proposal(proposal, config={"auto_mark_executed": False})
    cash_after_first = first["account"]["Cash"]
    qty_after_first = first["portfolio"].iloc[0]["PositionQty"]

    second = execute_approved_proposal(proposal, config={"auto_mark_executed": False})

    assert second["fill"]["RejectCode"] == "DUPLICATE_EXECUTION"
    assert second["account"]["Cash"] == cash_after_first
    assert second["portfolio"].iloc[0]["PositionQty"] == qty_after_first
    fills = load_csv(PAPER_FILLS_FILE, FILL_COLUMNS)
    assert (fills["FillStatus"] == "FILLED").sum() == 1


def test_max_open_positions_blocks_new_buy_but_allows_add_existing():
    portfolio = open_positions(count=5, include_buyok=True)

    rejected = execute_approved_proposal(
        approved_proposal(Symbol="NEW.BK", ProposalId="RM-SET-NEW-BUY-20260711"),
        portfolio=portfolio,
        config={"auto_mark_executed": False, "max_open_positions": 5},
    )
    assert rejected["fill"]["RejectCode"] == "MAX_OPEN_POSITIONS"

    added = execute_approved_proposal(
        approved_proposal(Action="ADD", Quantity=100, ProposalId="RM-SET-BUYOK-ADD-20260711"),
        portfolio=portfolio,
        config={"auto_mark_executed": False, "max_open_positions": 5},
    )
    assert added["fill"]["FillStatus"] == "FILLED"


def test_order_and_position_value_controls():
    max_order = execute_approved_proposal(
        approved_proposal(),
        config={"auto_mark_executed": False, "max_order_value_pct": 5, "max_position_value_pct": 100},
    )
    assert max_order["fill"]["RejectCode"] == "MAX_ORDER_VALUE"

    max_position = execute_approved_proposal(
        approved_proposal(ProposalId="RM-SET-POS-BUY-20260711", Symbol="POSLIMIT"),
        config={"auto_mark_executed": False, "max_order_value_pct": 100, "max_position_value_pct": 5},
    )
    assert max_position["fill"]["RejectCode"] == "MAX_POSITION_VALUE"


def test_daily_loss_limit_blocks_buy_and_add_but_allows_exit():
    seed_daily_loss_state()
    account = {"InitialCash": 100000, "Cash": 96000, "TotalEquity": 96000, "MarketValue": 0}

    buy = execute_approved_proposal(
        approved_proposal(ProposalId="RM-SET-LOCK-BUY-20260711", Symbol="LOCKBUY"),
        account=account,
        config={"auto_mark_executed": False, "daily_loss_limit_pct": 3},
    )
    assert buy["fill"]["RejectCode"] == "DAILY_LOSS_LIMIT_EXCEEDED"

    add = execute_approved_proposal(
        approved_proposal(Action="ADD", Quantity=100, ProposalId="RM-SET-BUYOK-ADD-20260711"),
        account=account,
        portfolio=pd.DataFrame([open_position()]),
        config={"auto_mark_executed": False, "daily_loss_limit_pct": 3},
    )
    assert add["fill"]["RejectCode"] == "DAILY_LOSS_LIMIT_EXCEEDED"

    exit_result = execute_approved_proposal(
        approved_proposal(Action="EXIT", ProposalId="RM-SET-BUYOK-EXIT-20260711"),
        account=account,
        portfolio=pd.DataFrame([open_position()]),
        config={"auto_mark_executed": False, "daily_loss_limit_pct": 3},
    )
    assert exit_result["fill"]["FillStatus"] == "FILLED"


def test_reject_codes_and_audit_are_append_only():
    execute_approved_proposal(approved_proposal(EntryPrice=0), config={"auto_mark_executed": False})
    events_after_reject = load_csv(PAPER_ORDER_EVENTS_FILE, ORDER_EVENT_COLUMNS)
    assert events_after_reject.iloc[-1]["RejectCode"] == "INVALID_PRICE"

    execute_approved_proposal(approved_proposal(ProposalId="RM-SET-GOOD-BUY-20260711", Symbol="GOOD"), config={"auto_mark_executed": False})
    events_after_fill = load_csv(PAPER_ORDER_EVENTS_FILE, ORDER_EVENT_COLUMNS)
    assert len(events_after_fill) > len(events_after_reject)


def test_scanner_source_has_no_paper_execution_call():
    scanner_source = (Path(__file__).resolve().parents[1] / "scanner.py").read_text(encoding="utf-8")

    assert "execute_approved_proposal" not in scanner_source
    assert "cancel_paper_order" not in scanner_source
