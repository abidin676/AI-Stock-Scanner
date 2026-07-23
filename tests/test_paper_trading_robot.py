from datetime import datetime
import json

import pandas as pd
import pytest

from approval_queue import approve_proposal, load_approval_queue
from paper_broker import PaperBrokerConfig, create_order, load_paper_broker_config
from paper_trading_robot import (
    THREE_RED_DAYS_EXIT_REASON,
    consecutive_red_days,
    load_fresh_position_daily_histories,
    run_paper_trading_robot,
    update_exit_tracking,
)
from risk_manager import RiskConfig


def robot_candidate(symbol="ROBOT.BK", **updates):
    row = {
        "Symbol": symbol,
        "Market": "SET",
        "ScanRunId": "scan-001",
        "LatestPriceDate": "2026-07-17",
        "CrossDate": "2026-07-17",
        "DaysSinceEMA9CrossEMA20": 0,
        "CrossAgeSource": "days_since_bullish_ema_cross",
        "EMA9": 10.2,
        "EMA20": 10.0,
        "PreviousEMA9": 9.9,
        "PreviousEMA20": 10.0,
        "BullishCrossEvent": True,
        "StrategySignal": "EARLY BUY",
        "LifecycleState": "EARLY",
        "AIDecision": "BUY",
        "QueueClass": "BUY",
        "EligibleForBuyQueue": True,
        "BaseEligible": True,
        "BlockingReasons": "",
        "AIBlockers": "",
        "AIRiskLevel": "LOW",
        "AIConfidence": 90,
        "PriorityScore": 90,
        "OpportunityScore": 85,
        "MarketQualityLabel": "HEALTHY",
        "RVOL": 1.5,
        "ExpansionScore": 10,
        "Price": 10,
        "Stop": 9,
        "Target": 13,
        "RR": 3,
    }
    row.update(updates)
    return row


def paths(tmp_path):
    return {
        "queue_path": tmp_path / "approval_queue.csv",
        "history_path": tmp_path / "approval_history.csv",
        "proposals_path": tmp_path / "robot_proposals.csv",
        "audit_path": tmp_path / "robot_audit.csv",
        "portfolio_path": tmp_path / "paper_portfolio.csv",
    }


def account(cash=100000):
    return {
        "InitialCash": 100000,
        "Cash": cash,
        "MarketValue": 0,
        "TotalEquity": cash,
        "OpenPositions": 0,
    }


def run_robot(rows, tmp_path, **kwargs):
    return run_paper_trading_robot(
        pd.DataFrame(rows),
        paper_account=kwargs.pop("paper_account", account()),
        paper_portfolio=kwargs.pop("paper_portfolio", pd.DataFrame()),
        risk_config=kwargs.pop("risk_config", RiskConfig()),
        paper_config=kwargs.pop("paper_config", PaperBrokerConfig()),
        daily_histories=kwargs.pop("daily_histories", {}),
        now=datetime(2026, 7, 18, 9, 0),
        persist=False,
        **paths(tmp_path),
        **kwargs,
    )


def test_strict_set_buy_passes_to_pending_approval(tmp_path):
    result = run_robot([robot_candidate()], tmp_path)

    assert len(result.proposals) == 1
    assert result.proposals.iloc[0]["ProposalStatus"] == "PENDING_APPROVAL"
    assert bool(result.proposals.iloc[0]["RiskApproved"]) is True
    assert result.queue.iloc[0]["Status"] == "PENDING_APPROVAL"
    assert result.queue.iloc[0]["Market"] == "SET"


@pytest.mark.parametrize(
    ("updates", "reason"),
    [
        ({"DaysSinceEMA9CrossEMA20": 3, "CrossDate": "2026-07-14", "BullishCrossEvent": False}, "CROSS_AGE_3"),
        ({"EMA9": 9.9}, "EMA9_NOT_ABOVE_EMA20"),
        ({"CrossDate": "", "DaysSinceEMA9CrossEMA20": None, "BullishCrossEvent": False}, "NO_BULLISH_CROSS_EVENT"),
        ({"RVOL": 1.49}, "RVOL_BELOW_SET_BUY_1.5X"),
        ({"ExpansionScore": 75}, "EXTENDED"),
        ({"AIDecision": "PREPARE"}, "AI_DECISION_NOT_BUY"),
        ({"Market": "USA"}, "EXECUTION_SCOPE_SET_ONLY"),
    ],
)
def test_hard_gate_never_creates_proposal(updates, reason, tmp_path):
    result = run_robot([robot_candidate(**updates)], tmp_path)

    assert result.proposals.empty
    assert result.queue.empty
    assert result.audit.iloc[0]["ExclusionReason"] == reason


def test_symbol_scan_run_duplicate_is_inserted_only_once(tmp_path):
    first = run_robot([robot_candidate()], tmp_path)
    second = run_robot([robot_candidate()], tmp_path)

    assert len(first.queue) == 1
    assert len(second.queue) == 1
    assert second.queue["RobotKey"].nunique() == 1
    assert second.proposals.empty
    assert second.audit.iloc[0]["ExclusionReason"] == "ACTIVE_ENTRY_PROPOSAL_EXISTS"


def test_paper_order_cannot_be_created_before_manual_approval(tmp_path, monkeypatch):
    import paper_broker

    monkeypatch.setattr(paper_broker, "PAPER_ORDERS_FILE", tmp_path / "orders.csv")
    result = run_robot([robot_candidate()], tmp_path)
    pending = result.queue.iloc[0].to_dict()

    blocked = create_order(pending, account=account(), portfolio=pd.DataFrame(), config=PaperBrokerConfig())
    assert blocked["Status"] == "REJECTED"
    assert blocked["RejectCode"] == "PROPOSAL_NOT_APPROVED"

    approve_proposal(
        pending["ProposalId"],
        queue_path=paths(tmp_path)["queue_path"],
        history_path=paths(tmp_path)["history_path"],
        now=datetime(2026, 7, 18, 9, 5),
    )
    approved = load_approval_queue(paths(tmp_path)["queue_path"]).iloc[0].to_dict()
    order = create_order(approved, account=account(), portfolio=pd.DataFrame(), config=PaperBrokerConfig())
    assert order["Status"] == "CREATED"
    assert order["OrderType"] == "MARKET_SIMULATED"


def open_position(symbol, value=10000):
    return {
        "Symbol": symbol,
        "Market": "SET",
        "PositionQty": 1000,
        "AverageCost": value / 1000,
        "LastPrice": value / 1000,
        "MarketValue": value,
        "PositionStatus": "OPEN",
    }


def daily_bars(*candles):
    return pd.DataFrame(
        [
            {
                "date": f"2026-07-{17 - len(candles) + index:02d}",
                "open": open_price,
                "close": close_price,
            }
            for index, (open_price, close_price) in enumerate(candles, start=1)
        ]
    )


def tracked_position(symbol="EXIT.BK"):
    return pd.DataFrame(
        [
            {
                **open_position(symbol),
                "AverageCost": 10,
                "LastPrice": 10,
                "StopPrice": 9,
                "TargetPrice": 13,
                "HighestPrice": 10,
                "TrailingStopPrice": 0,
            }
        ]
    )


def test_max_positions_is_checked_before_pending_proposal(tmp_path):
    portfolio = pd.DataFrame([open_position(f"P{i}.BK") for i in range(5)])
    result = run_robot(
        [robot_candidate()],
        tmp_path,
        paper_account=account(cash=50000),
        paper_portfolio=portfolio,
        paper_config=PaperBrokerConfig(max_open_positions=5),
    )

    assert result.proposals.iloc[0]["ProposalStatus"] == "REJECTED"
    assert result.proposals.iloc[0]["RejectReason"] == "MAX_OPEN_POSITIONS"
    assert result.queue.empty
    assert result.audit.iloc[0]["ExclusionReason"] == "MAX_OPEN_POSITIONS"


def test_existing_pending_proposals_are_reserved_before_new_risk_check(tmp_path):
    first = run_robot(
        [robot_candidate()],
        tmp_path,
        risk_config=RiskConfig(max_open_positions=1),
        paper_config=PaperBrokerConfig(max_open_positions=1),
    )
    second = run_robot(
        [robot_candidate(symbol="SECOND.BK", ScanRunId="scan-002")],
        tmp_path,
        risk_config=RiskConfig(max_open_positions=1),
        paper_config=PaperBrokerConfig(max_open_positions=1),
    )

    assert len(first.queue) == 1
    assert len(second.queue) == 1
    assert second.proposals.iloc[0]["ProposalStatus"] == "REJECTED"
    assert second.proposals.iloc[0]["RejectReason"] == "MAX_OPEN_POSITIONS"


def test_aggregate_exposure_and_cash_reserve_are_not_bypassed(tmp_path):
    rows = [robot_candidate(symbol=f"R{i}.BK", PriorityScore=100 - i) for i in range(4)]
    result = run_robot(
        rows,
        tmp_path,
        risk_config=RiskConfig(max_total_exposure_pct=20, max_open_positions=10),
        paper_config=PaperBrokerConfig(max_open_positions=10),
    )

    pending = result.proposals[result.proposals["ProposalStatus"] == "PENDING_APPROVAL"]
    rejected = result.proposals[result.proposals["ProposalStatus"] == "REJECTED"]
    assert pending["ProposedOrderValue"].sum() <= 20000
    assert not rejected.empty
    assert set(rejected["RejectReason"]) & {"MAX_TOTAL_EXPOSURE", "CASH_RESERVE_LIMIT", "BELOW_BOARD_LOT"}


@pytest.mark.parametrize(
    ("price", "expected"),
    [(89, "STOP_LOSS"), (121, "TARGET_REACHED"), (103, "TRAILING_STOP")],
)
def test_exit_monitor_tracks_stop_target_and_trailing(price, expected):
    portfolio = pd.DataFrame(
        [
            {
                **open_position("EXIT.BK", value=100000),
                "PositionQty": 1000,
                "AverageCost": 100,
                "LastPrice": 110,
                "MarketValue": 110000,
                "StopPrice": 90,
                "TargetPrice": 120,
                "HighestPrice": 110,
                "TrailingStopPrice": 104.5,
            }
        ]
    )
    updated, triggers = update_exit_tracking(portfolio, {"EXIT.BK": price}, PaperBrokerConfig())

    assert len(triggers) == 1
    assert triggers[0]["ExitReason"] == expected
    assert updated.iloc[0]["ExitReason"] == expected


def test_two_red_daily_bars_do_not_trigger_exit():
    history = daily_bars((11.5, 11.0), (11.0, 10.5))

    updated, triggers = update_exit_tracking(
        tracked_position(),
        {"EXIT.BK": 10.5},
        PaperBrokerConfig(),
        daily_histories={"EXIT.BK": history},
    )

    assert consecutive_red_days(history) == 2
    assert triggers == []
    assert updated.iloc[0]["ExitReason"] == ""


def test_three_red_daily_bars_create_pending_exit_proposal(tmp_path):
    history = daily_bars((12.0, 11.5), (11.5, 11.0), (11.0, 10.5))
    price_row = robot_candidate(
        symbol="EXIT.BK",
        AIDecision="WATCH",
        QueueClass="WATCH",
        EligibleForBuyQueue=False,
        BaseEligible=False,
        StrategySignal="WATCH",
        Price=10.5,
    )

    result = run_robot(
        [price_row],
        tmp_path,
        paper_portfolio=tracked_position(),
        paper_account=account(cash=90000),
        daily_histories={"EXIT.BK": history},
    )
    exit_proposal = result.proposals[
        result.proposals["AutomationType"] == "EXIT"
    ].iloc[0]

    assert exit_proposal["ProposalAction"] == "EXIT"
    assert exit_proposal["AutomationReason"] == THREE_RED_DAYS_EXIT_REASON
    assert exit_proposal["ProposalStatus"] == "PENDING_APPROVAL"
    assert result.queue.iloc[0]["Status"] == "PENDING_APPROVAL"
    assert result.queue.iloc[0]["AutomationReason"] == THREE_RED_DAYS_EXIT_REASON
    assert result.queue.iloc[0]["AIReason"] == "ปิดแดงต่อเนื่อง 3 วัน"
    assert result.portfolio.iloc[0]["PositionStatus"] == "OPEN"


def test_green_daily_bar_resets_consecutive_red_count():
    history = daily_bars(
        (12.0, 11.5),
        (11.4, 11.7),
        (11.7, 11.2),
        (11.2, 10.7),
    )

    _, triggers = update_exit_tracking(
        tracked_position(),
        {"EXIT.BK": 10.7},
        PaperBrokerConfig(),
        daily_histories={"EXIT.BK": history},
    )

    assert consecutive_red_days(history) == 2
    assert triggers == []


def test_stop_loss_has_priority_over_three_red_days():
    history = daily_bars((10.0, 9.7), (9.7, 9.2), (9.2, 8.5))

    _, triggers = update_exit_tracking(
        tracked_position(),
        {"EXIT.BK": 8.5},
        PaperBrokerConfig(),
        daily_histories={"EXIT.BK": history},
    )

    assert len(triggers) == 1
    assert triggers[0]["ExitReason"] == "STOP_LOSS"


def test_three_red_days_exit_can_be_disabled():
    history = daily_bars((12.0, 11.5), (11.5, 11.0), (11.0, 10.5))

    _, triggers = update_exit_tracking(
        tracked_position(),
        {"EXIT.BK": 10.5},
        PaperBrokerConfig(three_red_days_exit_enabled=False),
        daily_histories={"EXIT.BK": history},
    )

    assert triggers == []


def test_three_red_days_applies_only_to_open_held_set_position():
    history = daily_bars((12.0, 11.5), (11.5, 11.0), (11.0, 10.5))
    not_held = tracked_position()
    not_held.loc[0, "PositionStatus"] = "CLOSED"

    _, triggers = update_exit_tracking(
        not_held,
        {"EXIT.BK": 10.5},
        PaperBrokerConfig(),
        daily_histories={"EXIT.BK": history},
    )

    assert triggers == []


def test_three_red_days_config_loads_and_normalizes(tmp_path):
    config_path = tmp_path / "paper_broker_config.json"
    config_path.write_text(
        json.dumps(
            {
                "three_red_days_exit_enabled": True,
                "three_red_days_required": "3",
            }
        ),
        encoding="utf-8",
    )

    config = load_paper_broker_config(path=config_path)

    assert config.three_red_days_exit_enabled is True
    assert config.three_red_days_required == 3


def test_daily_history_loader_reads_only_fresh_open_set_position_cache(
    tmp_path,
    monkeypatch,
):
    history = daily_bars((12.0, 11.5), (11.5, 11.0), (11.0, 10.5))
    cache_path = tmp_path / "SET_HELD.csv"
    cache_path.write_text("fixture", encoding="utf-8")
    portfolio = pd.DataFrame(
        [
            open_position("HELD.BK"),
            {**open_position("CLOSED.BK"), "PositionStatus": "CLOSED"},
            {**open_position("AAPL"), "Market": "USA"},
        ]
    )
    requested = []

    def fake_cache_path(symbol, market, period, interval):
        requested.append((symbol, market, period, interval))
        return cache_path

    monkeypatch.setattr(
        "paper_trading_robot.price_cache_path",
        fake_cache_path,
    )
    monkeypatch.setattr(
        "paper_trading_robot.is_price_cache_fresh",
        lambda path: True,
    )
    monkeypatch.setattr(
        "paper_trading_robot.load_price_cache",
        lambda path: history,
    )

    histories = load_fresh_position_daily_histories(portfolio)

    assert requested == [("HELD.BK", "SET", "1y", "1d")]
    assert histories["HELD.BK"].equals(history)
    assert histories["HELD"].equals(history)


def test_exit_trigger_creates_pending_not_automatic_fill(tmp_path):
    portfolio = pd.DataFrame(
        [
            {
                **open_position("EXIT.BK"),
                "AverageCost": 10,
                "LastPrice": 10,
                "StopPrice": 9,
                "TargetPrice": 13,
                "HighestPrice": 11,
                "TrailingStopPrice": 10.45,
            }
        ]
    )
    price_row = robot_candidate(
        symbol="EXIT.BK",
        AIDecision="WATCH",
        QueueClass="WATCH",
        EligibleForBuyQueue=False,
        BaseEligible=False,
        StrategySignal="WATCH",
        Price=10,
    )
    result = run_robot([price_row], tmp_path, paper_portfolio=portfolio, paper_account=account(cash=90000))
    exits = result.proposals[result.proposals["AutomationType"] == "EXIT"]

    assert len(exits) == 1
    assert exits.iloc[0]["ProposalStatus"] == "PENDING_APPROVAL"
    assert result.queue.iloc[0]["Status"] == "PENDING_APPROVAL"
    assert result.portfolio.iloc[0]["PositionStatus"] == "OPEN"


def test_safety_config_cannot_enable_non_paper_or_automatic_execution(tmp_path):
    with pytest.raises(ValueError, match="PAPER_ONLY_MANUAL_EXECUTION_REQUIRED"):
        run_robot([robot_candidate()], tmp_path, paper_config=PaperBrokerConfig(paper_only=False))

    with pytest.raises(ValueError, match="PAPER_ONLY_MANUAL_EXECUTION_REQUIRED"):
        run_robot([robot_candidate()], tmp_path, paper_config=PaperBrokerConfig(execution_mode="AUTO"))


def test_robot_tagged_order_cannot_execute_outside_set():
    proposal = {
        "ProposalId": "ptr-usa",
        "RobotKey": "USA|AAPL|scan-1",
        "Symbol": "AAPL",
        "Market": "USA",
        "Action": "BUY",
        "Status": "APPROVED",
        "Quantity": 1,
        "EntryPrice": 100,
    }
    order = create_order(proposal, account=account(), portfolio=pd.DataFrame(), config=PaperBrokerConfig())

    assert order["Status"] == "REJECTED"
    assert order["RejectCode"] == "ROBOT_MARKET_NOT_ALLOWED"
