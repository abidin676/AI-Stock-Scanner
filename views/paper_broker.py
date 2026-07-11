import pandas as pd
import streamlit as st

from approval_queue import load_approval_queue, ready_for_paper_broker
from paper_broker import (
    CASH_LEDGER_COLUMNS,
    EXECUTION_HISTORY_COLUMNS,
    FILL_COLUMNS,
    ORDER_COLUMNS,
    ORDER_EVENT_COLUMNS,
    PAPER_CASH_LEDGER_FILE,
    PAPER_EXECUTION_HISTORY_FILE,
    PAPER_FILLS_FILE,
    PAPER_ORDER_EVENTS_FILE,
    PAPER_ORDERS_FILE,
    PAPER_TRADES_FILE,
    TERMINAL_ORDER_STATUSES,
    TRADE_COLUMNS,
    cancel_paper_order,
    execute_approved_proposal,
    load_csv,
    load_daily_state,
    load_paper_broker_config,
)
from paper_portfolio import (
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
        status_col = ""
        for candidate in ["Status", "OrderStatus", "FillStatus", "ExecutionStatus", "EventType"]:
            if candidate in df.columns:
                status_col = candidate
                break
        status_values = sorted([v for v in df.get(status_col, pd.Series(dtype=str)).dropna().astype(str).unique() if v]) if status_col else []
        status = columns[3].selectbox("Status", ["ALL"] + status_values, key=f"{prefix}_status")
        date = columns[4].text_input("Date", placeholder="YYYY-MM-DD", key=f"{prefix}_date")

    filtered = df.copy()
    if market != "ALL" and "Market" in filtered.columns:
        filtered = filtered[filtered["Market"].astype(str) == market]
    if symbol.strip() and "Symbol" in filtered.columns:
        filtered = filtered[filtered["Symbol"].astype(str).str.upper().str.contains(symbol.strip().upper(), na=False)]
    if action != "ALL" and "Action" in filtered.columns:
        filtered = filtered[filtered["Action"].astype(str) == action]
    if status != "ALL" and status_col:
        filtered = filtered[filtered[status_col].astype(str) == status]
    if date.strip():
        date_cols = [c for c in ["CreatedTime", "SubmittedTime", "FilledTime", "EventTime", "ExecutionTime"] if c in filtered.columns]
        if date_cols:
            mask = False
            for column in date_cols:
                mask = mask | filtered[column].astype(str).str.startswith(date.strip(), na=False)
            filtered = filtered[mask]
    return filtered


def render_account_summary():
    config = load_paper_broker_config()
    account = load_paper_account(config=config)
    portfolio = load_paper_portfolio()
    summary = calculate_portfolio_summary(portfolio, account)
    daily_state = load_daily_state(account, config, persist=False)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cash", f"{summary['Cash']:,.2f}")
    c2.metric("Market Value", f"{summary['MarketValue']:,.2f}")
    c3.metric("Equity", f"{summary['TotalEquity']:,.2f}")
    c4.metric("Open Positions", int(summary["OpenPositions"]))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Realized P/L", f"{summary['RealizedPnL']:,.2f}")
    c2.metric("Unrealized P/L", f"{summary['UnrealizedPnL']:,.2f}")
    c3.metric("Daily P/L", f"{safe_number(daily_state.get('DailyPnL')):,.2f}")
    c4.metric("Daily P/L %", f"{safe_number(daily_state.get('DailyPnLPct')):,.2f}%")

    c1, c2, c3 = st.columns(3)
    c1.metric("Max Open Positions", int(config.max_open_positions))
    c2.metric("Daily Loss Limit", f"{config.daily_loss_limit_pct:.2f}%")
    c3.metric("Daily Loss Control", "LOCKED" if daily_state.get("LossLimitTriggered") else "OK")


def render_risk_controls():
    config = load_paper_broker_config()
    st.subheader("Risk Controls")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Max Open Positions", int(config.max_open_positions))
    c2.metric("Max Position Value", f"{config.max_position_value_pct:.2f}%")
    c3.metric("Max Order Value", f"{config.max_order_value_pct:.2f}%")
    c4.metric("Daily Loss Limit", f"{config.daily_loss_limit_pct:.2f}%")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Allow Negative Cash", str(bool(config.allow_negative_cash)))
    c2.metric("Allow Short", str(bool(config.allow_short_selling)))
    c3.metric("Allow Add", str(bool(config.allow_add)))
    c4.metric("Allow Reduce", str(bool(config.allow_reduce)))


def render_ready_proposals():
    queue = load_approval_queue()
    ready = ready_for_paper_broker(queue)
    st.subheader("Eligible Proposals")

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
        st.info("No approved proposals eligible for paper order creation.")
    else:
        st.dataframe(ready[[c for c in columns if c in ready.columns]], use_container_width=True, hide_index=True)

    return ready


def render_manual_execution(ready):
    st.subheader("Create And Execute")
    st.warning("PAPER TRADING ONLY - NO REAL BROKER ORDER WILL BE SENT")

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
        "I understand this creates a simulated paper order only.",
        key=f"paper_confirm_{proposal['ProposalId']}",
    )

    if st.button("Create and Execute Paper Order", disabled=not confirm, key=f"paper_execute_{proposal['ProposalId']}"):
        try:
            result = execute_approved_proposal(proposal)
            fill = result["fill"]
            if fill["FillStatus"] == "REJECTED":
                st.error(f"Paper order rejected: {fill.get('RejectCode', '')} - {fill['RejectReason']}")
            else:
                st.success(f"Paper order filled: {fill['FilledQty']:g} {fill['Symbol']} @ {fill['FillPrice']:,.2f}")
            st.rerun()
        except Exception as exc:
            st.error(f"Paper execution failed: {exc}")


def render_open_orders():
    st.subheader("Open Paper Orders")
    orders = load_csv(PAPER_ORDERS_FILE, ORDER_COLUMNS)
    if orders.empty:
        st.info("No open paper orders.")
        return

    status = orders.get("Status", orders.get("OrderStatus", pd.Series(dtype=str))).astype(str).str.upper()
    open_orders = orders[~status.isin(TERMINAL_ORDER_STATUSES)].copy()
    if open_orders.empty:
        st.info("No open paper orders.")
        return

    columns = [
        "PaperOrderId",
        "ProposalId",
        "Symbol",
        "Market",
        "Action",
        "RequestedQty",
        "ReferencePrice",
        "Status",
        "CreatedTime",
        "SubmittedTime",
    ]
    st.dataframe(open_orders[[c for c in columns if c in open_orders.columns]], use_container_width=True, hide_index=True)

    selected = st.selectbox("Cancel Paper Order", open_orders["PaperOrderId"].astype(str).tolist(), key="paper_cancel_select")
    reason = st.text_input("Cancel Reason", value="manual_cancel", key="paper_cancel_reason")
    confirm = st.checkbox("Confirm simulated order cancellation.", key=f"paper_cancel_confirm_{selected}")
    if st.button("Cancel Paper Order", disabled=not confirm, key=f"paper_cancel_button_{selected}"):
        try:
            cancel_paper_order(selected, reason=reason, triggered_by="dashboard")
            st.success("Paper order cancelled.")
            st.rerun()
        except Exception as exc:
            st.error(f"Cancellation failed: {exc}")


def render_runtime_tables():
    tabs = st.tabs(["Order History", "Fills", "Portfolio", "Trade Ledger", "Audit Events", "Execution History", "Cash Ledger"])

    with tabs[0]:
        orders = load_csv(PAPER_ORDERS_FILE, ORDER_COLUMNS)
        columns = [
            "PaperOrderId",
            "ProposalId",
            "Symbol",
            "Action",
            "RequestedQty",
            "Status",
            "ReferencePrice",
            "FillPrice",
            "Commission",
            "RejectCode",
            "CreatedTime",
            "SubmittedTime",
            "FilledTime",
        ]
        orders = filter_table(orders, "paper_orders")
        st.dataframe(orders[[c for c in columns if c in orders.columns]], use_container_width=True, hide_index=True)

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
        events = load_csv(PAPER_ORDER_EVENTS_FILE, ORDER_EVENT_COLUMNS)
        events = filter_table(events, "paper_events")
        st.dataframe(events, use_container_width=True, hide_index=True)

    with tabs[5]:
        history = load_csv(PAPER_EXECUTION_HISTORY_FILE, EXECUTION_HISTORY_COLUMNS)
        history = filter_table(history, "paper_history")
        st.dataframe(history, use_container_width=True, hide_index=True)

    with tabs[6]:
        cash = load_csv(PAPER_CASH_LEDGER_FILE, CASH_LEDGER_COLUMNS)
        st.dataframe(cash, use_container_width=True, hide_index=True)


def paper_broker_page():
    st.title("Paper Broker")
    st.caption("Controlled simulated order lifecycle after Approval Queue.")
    st.warning("PAPER TRADING ONLY - NO REAL BROKER ORDER WILL BE SENT")

    render_account_summary()
    render_risk_controls()
    ready = render_ready_proposals()
    render_manual_execution(ready)
    render_open_orders()
    render_runtime_tables()
