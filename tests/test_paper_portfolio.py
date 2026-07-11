import pandas as pd
import pytest

from paper_portfolio import (
    PAPER_ACCOUNT_FILE,
    PAPER_PORTFOLIO_FILE,
    apply_fill_to_portfolio,
    atomic_write_csv,
    calculate_portfolio_summary,
    load_paper_account,
    load_paper_portfolio,
    save_paper_account,
    save_paper_portfolio,
    update_paper_market_prices,
)


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def base_fill(**updates):
    fill = {
        "FillId": "PF-SET-BUYOK-BUY-20260711-abc123",
        "PaperOrderId": "PO-SET-BUYOK-BUY-20260711-abc123",
        "ProposalId": "RM-SET-BUYOK-BUY-20260711",
        "Symbol": "BUYOK",
        "Market": "SET",
        "Action": "BUY",
        "Side": "BUY",
        "RequestedQty": 1000,
        "FilledQty": 1000,
        "UnfilledQty": 0,
        "ReferencePrice": 10,
        "FillPrice": 10.01,
        "GrossValue": 10010,
        "Commission": 15.7157,
        "SlippageCost": 10,
        "NetCashFlow": -10025.7157,
        "RealizedPnL": 0,
        "FillStatus": "FILLED",
        "RejectReason": "NONE",
        "FillTime": "2026-07-11T09:30:00",
        "StopPrice": 9,
        "TargetPrice": 13,
        "PaperBrokerVersion": "1.0",
    }
    fill.update(updates)
    return fill


def open_position():
    return pd.DataFrame(
        [
            {
                "Symbol": "BUYOK",
                "Market": "SET",
                "PositionQty": 1000,
                "AverageCost": 10,
                "LastPrice": 10,
                "MarketValue": 10000,
                "CostBasis": 10000,
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


def test_account_persists_across_reload():
    account = load_paper_account()
    account["Cash"] = 90000
    save_paper_account(account)

    loaded = load_paper_account()

    assert loaded["Cash"] == 90000
    assert loaded["InitialCash"] == 100000


def test_portfolio_persists_across_reload():
    save_paper_portfolio(open_position())
    loaded = load_paper_portfolio()

    assert loaded.iloc[0]["Symbol"] == "BUYOK"
    assert loaded.iloc[0]["PositionQty"] == 1000


def test_closed_position_reloads_correctly():
    portfolio = open_position()
    portfolio.at[0, "PositionQty"] = 0
    portfolio.at[0, "PositionStatus"] = "CLOSED"
    save_paper_portfolio(portfolio)

    loaded = load_paper_portfolio()

    assert loaded.iloc[0]["PositionStatus"] == "CLOSED"
    assert loaded.iloc[0]["PositionQty"] == 0


def test_apply_buy_fill_updates_account_and_position():
    portfolio, account, trade, cash_row = apply_fill_to_portfolio(base_fill(), pd.DataFrame(), load_paper_account())

    assert portfolio.iloc[0]["PositionQty"] == 1000
    assert account["Cash"] < 100000
    assert trade["Quantity"] == 1000
    assert cash_row["TransactionType"] == "BUY"


def test_apply_reduce_fill_updates_realized_pnl():
    fill = base_fill(
        Action="REDUCE",
        Side="SELL",
        FilledQty=500,
        FillPrice=11,
        GrossValue=5500,
        Commission=8,
        NetCashFlow=5492,
    )
    portfolio, account, trade, _ = apply_fill_to_portfolio(fill, open_position(), load_paper_account())

    assert portfolio.iloc[0]["PositionQty"] == 500
    assert trade["RealizedPnL"] == 492
    assert account["Cash"] == 105492


def test_apply_exit_fill_closes_position():
    fill = base_fill(
        Action="EXIT",
        Side="SELL",
        FilledQty=1000,
        FillPrice=11,
        GrossValue=11000,
        Commission=10,
        NetCashFlow=10990,
    )
    portfolio, account, trade, _ = apply_fill_to_portfolio(fill, open_position(), load_paper_account())

    assert portfolio.iloc[0]["PositionStatus"] == "CLOSED"
    assert portfolio.iloc[0]["AverageCost"] == 0
    assert trade["PositionQtyAfter"] == 0


def test_unrealized_pnl_calculation_is_correct():
    portfolio = update_paper_market_prices(open_position(), {"BUYOK": 12})

    assert portfolio.iloc[0]["UnrealizedPnL"] == 2000
    assert portfolio.iloc[0]["UnrealizedReturnPct"] == 20


def test_total_equity_and_return_percentage_are_correct():
    account = load_paper_account()
    account["Cash"] = 90000
    portfolio = update_paper_market_prices(open_position(), {"BUYOK": 12})
    summary = calculate_portfolio_summary(portfolio, account)

    assert summary["TotalEquity"] == 102000
    assert summary["TotalReturnPct"] == 2


def test_portfolio_summary_counts_winners_and_losers():
    first = open_position()
    second = open_position()
    second.at[0, "Symbol"] = "LOSS"
    second.at[0, "LastPrice"] = 8
    portfolio = pd.concat([first, second], ignore_index=True)
    portfolio = update_paper_market_prices(portfolio, {"BUYOK": 12, "LOSS": 8})
    summary = calculate_portfolio_summary(portfolio, load_paper_account())

    assert summary["WinningPositions"] == 1
    assert summary["LosingPositions"] == 1


def test_input_portfolio_is_not_modified_in_place():
    portfolio = open_position()
    original = portfolio.copy(deep=True)
    apply_fill_to_portfolio(base_fill(Action="ADD"), portfolio, load_paper_account())

    pd.testing.assert_frame_equal(portfolio, original)


def test_atomic_write_helper_preserves_existing_file_on_failure(monkeypatch):
    df = pd.DataFrame([{"A": 1}])
    atomic_write_csv(df, PAPER_PORTFOLIO_FILE)

    def fail_replace(self, path):
        raise OSError("replace failed")

    tmp_path_type = type(PAPER_PORTFOLIO_FILE.with_name(".paper_portfolio.csv.tmp"))
    monkeypatch.setattr(tmp_path_type, "replace", fail_replace, raising=False)

    with pytest.raises(OSError):
        atomic_write_csv(pd.DataFrame([{"A": 2}]), PAPER_PORTFOLIO_FILE)

    loaded = pd.read_csv(PAPER_PORTFOLIO_FILE)
    assert loaded.iloc[0]["A"] == 1
