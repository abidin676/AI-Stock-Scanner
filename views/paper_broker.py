import pandas as pd
import streamlit as st

from approval_queue import load_approval_queue, ready_for_paper_broker
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
    TRADE_COLUMNS,
    execute_approved_proposal,
    load_csv,
    load_paper_broker_config,
)
from paper_portfolio import (
    PORTFOLIO_COLUMNS,
    calculate_portfolio_summary,
    load_paper_account,
    load_paper_portfolio,
)


def safe_number(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def filter_table(df, prefix):
    if df.empty:
        return df

    with st.expander("Filters", expanded=False):
        columns = st.columns(5)
        market = columns[0].selectbox(
            "Market",
            ["ALL"] + sorted([v for v in df.get("Market", pd.Series(dtype=str)).dropna().astype(str).unique() if v]),
            key=f"{prefix}_market",
        )
        symbol = columns[1].text_input("Symbol", key=f"{prefix}_symbol")
        action_values = sorted([v for v in df.get("Action", pd.Series(dtype=str)).dropna().astype(str).unique() if v])
        action = columns[2].selectbox("Action", ["ALL"] + action_values, key=f"{prefix}_action")
        side_values = sorted([v for v in df.get("Side", pd.Series(dtype=str)).dropna().astype(str).unique() if v])
        side = columns[3].selectbox("Side", ["ALL"] + side_values, key=f"{prefix}_side")
        status_col = "OrderStatus" if "OrderStatus" in df.columns else "FillStatus" if "FillStatus" in df.columns else "ExecutionStatus" if "ExecutionStatus" in df.columns else ""
        status_values = sorted([v for v in df.get(status_col, pd.Series(dtype=str)).dropna().astype(str).unique() if v]) if status_col else []
        status = columns[4].selectbox("Status", ["ALL"] + status_values, key=f"{prefix}_status")

    filtered = df.copy()
    if market != "ALL" and "Market" in filtered.columns:
        filtered = filtered[filtered["Market"].astype(str) == market]
    if symbol.strip() and "Symbol" in filtered.columns:
        filtered = filtered[filtered["Symbol"].astype(str).str.upper().str.contains(symbol.strip().upper(), na=False)]
    if action != "ALL" and "Action" in filtered.columns:
        filtered = filtered[filtered["Action"].astype(str) == action]
    if side != "ALL" and "Side" in filtered.columns:
        filtered = filtered[filtered["Side"].astype(str) == side]
    if status != "ALL" and status_col:
        filtered = filtered[filtered[status_col].astype(str) == status]
    return filtered


def render_account_summary():
    config = load_paper_broker_config()
    account = load_paper_account(config=config)
    portfolio = load_paper_portfolio()
    summary = calculate_portfolio_summary(portfolio, account)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cash", f"{summary['Cash']:,.2f}")
    c2.metric("Buying Power", f"{safe_number(account.get('BuyingPower')):,.2f}")
    c3.metric("Market Value", f"{summary['MarketValue']:,.2f}")
    c4.metric("Total Equity", f"{summary['TotalEquity']:,.2f}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Realized P&L", f"{summary['RealizedPnL']:,.2f}")
    c2.metric("Unrealized P&L", f"{summary['UnrealizedPnL']:,.2f}")
    c3.metric("Open Positions", int(summary["OpenPositions"]))
    c4.metric("Total Commission", f"{summary['TotalCommission']:,.2f}")


def render_ready_proposals():
    queue = load_approval_queue()
    ready = ready_for_paper_broker(queue)
    st.subheader("Approved Proposals Ready")

    columns = [
        "ProposalId",
        "Symbol",
        "Market",
        "Action",
        "Quantity",
        "EntryPrice",
        "StopPrice",
        "TargetPrice",
        "ProposedOrderValue",
        "AIConfidence",
        "RiskScore",
        "ApprovedTime",
        "ExpireTime",
    ]

    if ready.empty:
        st.info("No approved proposals ready for paper execution.")
    else:
        st.dataframe(ready[[c for c in columns if c in ready.columns]], use_container_width=True, hide_index=True)

    return ready


def render_manual_execution(ready):
    st.subheader("Manual Execution")
    st.warning("Paper Broker simulates trades only. No real broker order is sent.")

    if ready.empty:
        return

    labels = [
        f"{row.ProposalId} | {row.Symbol} | {row.Action} | {row.Quantity:g}"
        for row in ready.itertuples()
    ]
    selected = st.selectbox("Select Approved Proposal", labels, key="paper_execute_select")
    proposal = ready.iloc[labels.index(selected)].to_dict()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Symbol", proposal["Symbol"])
    c2.metric("Action", proposal["Action"])
    c3.metric("Qty", f"{safe_number(proposal['Quantity']):,.2f}")
    c4.metric("Entry", f"{safe_number(proposal['EntryPrice']):,.2f}")

    confirm = st.checkbox(
        "I understand this is a simulated paper trade.",
        key=f"paper_confirm_{proposal['ProposalId']}",
    )

    if st.button("Execute Paper Order", disabled=not confirm, key=f"paper_execute_{proposal['ProposalId']}"):
        try:
            result = execute_approved_proposal(proposal)
            fill = result["fill"]
            if fill["FillStatus"] == "REJECTED":
                st.error(f"Paper order rejected: {fill['RejectReason']}")
            else:
                st.success(f"Paper order filled: {fill['FilledQty']:g} {fill['Symbol']} @ {fill['FillPrice']:,.2f}")
            st.rerun()
        except Exception as exc:
            st.error(f"Paper execution failed: {exc}")


def render_runtime_tables():
    tabs = st.tabs(["Paper Orders", "Paper Fills", "Paper Portfolio", "Trade Ledger", "Execution History", "Cash Ledger"])

    with tabs[0]:
        orders = load_csv(PAPER_ORDERS_FILE, ORDER_COLUMNS)
        orders = filter_table(orders, "paper_orders")
        st.dataframe(orders, use_container_width=True, hide_index=True)

    with tabs[1]:
        fills = load_csv(PAPER_FILLS_FILE, FILL_COLUMNS)
        fills = filter_table(fills, "paper_fills")
        st.dataframe(fills, use_container_width=True, hide_index=True)

    with tabs[2]:
        portfolio = load_paper_portfolio()
        columns = [
            "Symbol",
            "Market",
            "PositionQty",
            "AverageCost",
            "LastPrice",
            "MarketValue",
            "UnrealizedPnL",
            "UnrealizedReturnPct",
            "RealizedPnL",
            "StopPrice",
            "TargetPrice",
            "PositionStatus",
        ]
        st.dataframe(portfolio[[c for c in columns if c in portfolio.columns]], use_container_width=True, hide_index=True)

    with tabs[3]:
        trades = load_csv(PAPER_TRADES_FILE, TRADE_COLUMNS)
        columns = [
            "TradeId",
            "Symbol",
            "Action",
            "Quantity",
            "FillPrice",
            "Commission",
            "RealizedPnL",
            "CashBefore",
            "CashAfter",
            "TradeTime",
        ]
        st.dataframe(trades[[c for c in columns if c in trades.columns]], use_container_width=True, hide_index=True)

    with tabs[4]:
        history = load_csv(PAPER_EXECUTION_HISTORY_FILE, EXECUTION_HISTORY_COLUMNS)
        history = filter_table(history, "paper_history")
        st.dataframe(history, use_container_width=True, hide_index=True)

    with tabs[5]:
        cash = load_csv(PAPER_CASH_LEDGER_FILE, CASH_LEDGER_COLUMNS)
        st.dataframe(cash, use_container_width=True, hide_index=True)


def paper_broker_page():
    st.title("Paper Broker")
    st.caption("Deterministic simulated execution layer after Approval Queue.")
    st.warning("Paper Broker simulates trades only. No real broker order is sent.")

    render_account_summary()
    ready = render_ready_proposals()
    render_manual_execution(ready)
    render_runtime_tables()
