from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from approval_queue import (
    approve_proposal,
    cancel_proposal,
    load_approval_queue,
    reject_proposal,
)
from paper_broker import (
    ORDER_COLUMNS,
    PAPER_ORDERS_FILE,
    execute_approved_proposal,
    load_csv,
    load_paper_broker_config,
)
from paper_portfolio import calculate_portfolio_summary, load_paper_account, load_paper_portfolio
from paper_trading_robot import (
    AUDIT_COLUMNS,
    ROBOT_AUDIT_FILE,
    exit_reason_label,
)


DISPLAY_STATUSES = ["PENDING", "APPROVED", "FILLED", "REJECTED", "CANCELLED", "EXPIRED"]


def _read_audit(path: Path = ROBOT_AUDIT_FILE) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=AUDIT_COLUMNS)
    try:
        data = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=AUDIT_COLUMNS)
    for column in AUDIT_COLUMNS:
        if column not in data.columns:
            data[column] = ""
    return data


def build_paper_trading_status_table(
    queue: pd.DataFrame | None,
    orders: pd.DataFrame | None,
    audit: pd.DataFrame | None,
) -> pd.DataFrame:
    queue_df = queue.copy() if queue is not None else pd.DataFrame()
    order_df = orders.copy() if orders is not None else pd.DataFrame()
    audit_df = audit.copy() if audit is not None else pd.DataFrame()
    records: list[dict] = []

    order_by_proposal: dict[str, dict] = {}
    if not order_df.empty and "ProposalId" in order_df.columns:
        for _, order in order_df.iterrows():
            order_by_proposal[str(order.get("ProposalId", "")).strip()] = order.to_dict()

    queued_keys: set[tuple[str, str, str]] = set()
    for _, item in queue_df.iterrows():
        row = item.to_dict()
        proposal_id = str(row.get("ProposalId", "")).strip()
        raw_status = str(row.get("Status", "")).strip().upper()
        status = {
            "PENDING_APPROVAL": "PENDING",
            "APPROVED": "APPROVED",
            "EXECUTED": "FILLED",
        }.get(raw_status, raw_status)
        order = order_by_proposal.get(proposal_id, {})
        if str(order.get("Status", order.get("OrderStatus", ""))).upper() == "FILLED":
            status = "FILLED"
        raw_reason = (
            str(row.get("RejectedReason", "")).strip()
            or str(row.get("AutomationReason", "")).strip()
            or str(row.get("RiskManagerReason", "")).strip()
        )
        reason = exit_reason_label(raw_reason)
        records.append(
            {
                "ProposalId": proposal_id,
                "ScanRunId": str(row.get("ScanRunId", "")).strip(),
                "Symbol": str(row.get("Symbol", "")).strip(),
                "Market": str(row.get("Market", "")).strip(),
                "Action": str(row.get("Action", "")).strip(),
                "Status": status,
                "Quantity": row.get("Quantity", 0),
                "EntryPrice": row.get("EntryPrice", 0),
                "StopPrice": row.get("StopPrice", 0),
                "TargetPrice": row.get("TargetPrice", 0),
                "Reason": reason,
                "CreatedTime": row.get("CreatedTime", ""),
                "ApprovedTime": row.get("ApprovedTime", ""),
                "ExecutedTime": row.get("ExecutedTime", ""),
                "PaperOrderId": order.get("PaperOrderId", row.get("PaperOrderId", "")),
                "FillId": order.get("FillId", row.get("FillId", "")),
            }
        )
        queued_keys.add(
            (
                str(row.get("Symbol", "")).strip().upper(),
                str(row.get("ScanRunId", "")).strip(),
                str(row.get("AutomationType", "ENTRY")).strip().upper(),
            )
        )

    for _, item in audit_df.iterrows():
        row = item.to_dict()
        reason = str(row.get("ExclusionReason", "")).strip()
        if not reason:
            continue
        key = (
            str(row.get("Symbol", "")).strip().upper(),
            str(row.get("ScanRunId", "")).strip(),
            str(row.get("AutomationType", "ENTRY")).strip().upper(),
        )
        if key in queued_keys:
            continue
        records.append(
            {
                "ProposalId": str(row.get("ProposalId", "")).strip(),
                "ScanRunId": key[1],
                "Symbol": key[0],
                "Market": str(row.get("Market", "")).strip(),
                "Action": key[2],
                "Status": "REJECTED",
                "Quantity": 0,
                "EntryPrice": 0,
                "StopPrice": 0,
                "TargetPrice": 0,
                "Reason": reason,
                "CreatedTime": row.get("AuditTime", ""),
                "ApprovedTime": "",
                "ExecutedTime": "",
                "PaperOrderId": "",
                "FillId": "",
            }
        )

    output = pd.DataFrame(records)
    if output.empty:
        return pd.DataFrame(
            columns=[
                "ProposalId", "ScanRunId", "Symbol", "Market", "Action", "Status",
                "Quantity", "EntryPrice", "StopPrice", "TargetPrice", "Reason",
                "CreatedTime", "ApprovedTime", "ExecutedTime", "PaperOrderId", "FillId",
            ]
        )
    order = {value: idx for idx, value in enumerate(DISPLAY_STATUSES)}
    output["_StatusOrder"] = output["Status"].map(order).fillna(len(order))
    return output.sort_values(
        ["_StatusOrder", "CreatedTime", "Symbol"],
        ascending=[True, False, True],
        kind="mergesort",
    ).drop(columns="_StatusOrder").reset_index(drop=True)


def _render_account() -> None:
    config = load_paper_broker_config()
    account = load_paper_account(config=config)
    portfolio = load_paper_portfolio()
    summary = calculate_portfolio_summary(portfolio, account)
    first_row = st.columns(2)
    first_row[0].metric("Cash", f"{summary['Cash']:,.2f}")
    first_row[1].metric("Market Value", f"{summary['MarketValue']:,.2f}")
    second_row = st.columns(2)
    second_row[0].metric("Equity", f"{summary['TotalEquity']:,.2f}")
    second_row[1].metric("Open Positions", int(summary["OpenPositions"]))
    st.caption("Execution mode: PAPER / MANUAL APPROVAL + MANUAL FILL")


def _render_manual_controls(queue: pd.DataFrame) -> None:
    st.subheader("Manual Approval & Fill")
    pending = queue[queue["Status"].astype(str).str.upper() == "PENDING_APPROVAL"].copy()
    approved = queue[queue["Status"].astype(str).str.upper() == "APPROVED"].copy()

    if pending.empty:
        st.info("ไม่มี proposal ที่รออนุมัติ")
    else:
        labels = [f"{row.ProposalId} | {row.Symbol} | {row.Action}" for row in pending.itertuples()]
        selected = st.selectbox("Pending proposal", labels, key="paper_robot_pending")
        proposal = pending.iloc[labels.index(selected)].to_dict()
        reason = st.text_input("เหตุผลกรณี Reject/Cancel", value="Manual decision", key="paper_robot_reason")
        c1, c2, c3 = st.columns(3)
        if c1.button("Approve", type="primary", key=f"robot_approve_{proposal['ProposalId']}"):
            approve_proposal(proposal["ProposalId"], approved_by="dashboard")
            st.success("อนุมัติแล้ว — ยังไม่มีการ fill จนกว่าจะกด Fill Paper Order")
            st.rerun()
        if c2.button("Reject", key=f"robot_reject_{proposal['ProposalId']}"):
            reject_proposal(proposal["ProposalId"], rejected_by="dashboard", reason=reason)
            st.rerun()
        if c3.button("Cancel", key=f"robot_cancel_{proposal['ProposalId']}"):
            cancel_proposal(proposal["ProposalId"], cancelled_by="dashboard", reason=reason)
            st.rerun()

    st.markdown("---")
    if approved.empty:
        st.info("ไม่มี proposal ที่อนุมัติแล้วรอ fill")
        return

    labels = [f"{row.ProposalId} | {row.Symbol} | {row.Action}" for row in approved.itertuples()]
    selected = st.selectbox("Approved proposal", labels, key="paper_robot_approved")
    proposal = approved.iloc[labels.index(selected)].to_dict()
    confirmed = st.checkbox(
        "ยืนยันว่าเป็น Paper Trade เท่านั้น และต้องการ Fill รายการนี้",
        key=f"robot_fill_confirm_{proposal['ProposalId']}",
    )
    if st.button(
        "Fill Paper Order",
        disabled=not confirmed,
        key=f"robot_fill_{proposal['ProposalId']}",
    ):
        result = execute_approved_proposal(proposal)
        fill = result["fill"]
        if str(fill.get("FillStatus", "")).upper() == "REJECTED":
            st.error(f"Paper fill rejected: {fill.get('RejectCode', '')} — {fill.get('RejectReason', '')}")
        else:
            st.success(f"Paper fill สำเร็จ: {fill.get('FilledQty', 0):g} {fill.get('Symbol', '')} @ {fill.get('FillPrice', 0):,.2f}")
        st.rerun()


def paper_trading_page() -> None:
    st.title("River Alpha Paper Trading")
    st.caption("SET only · Approval Queue required · Manual paper fill only")
    st.warning("PAPER TRADING ONLY — ระบบนี้ไม่เชื่อมต่อและไม่ส่งคำสั่งไปโบรกเกอร์จริง")

    config = load_paper_broker_config()
    paper_only = getattr(config, "paper_only", False)
    execution_mode = str(getattr(config, "execution_mode", "")).upper()
    if paper_only is not True or execution_mode != "MANUAL":
        st.error(
            "Live broker execution ไม่รองรับ — "
            "Paper Trading ต้องใช้ paper_only=true และ execution_mode=MANUAL เท่านั้น"
        )
        st.stop()

    _render_account()
    queue = load_approval_queue()
    if not queue.empty:
        queue = queue[
            (queue["Market"].astype(str).str.upper() == "SET")
            & (queue["RobotKey"].astype(str).str.strip() != "")
        ].copy()
    orders = load_csv(PAPER_ORDERS_FILE, ORDER_COLUMNS)
    audit = _read_audit()
    status_table = build_paper_trading_status_table(queue, orders, audit)

    st.subheader("Proposal Status")
    selected_status = st.multiselect("Status", DISPLAY_STATUSES, default=DISPLAY_STATUSES)
    visible = status_table[status_table["Status"].isin(selected_status)] if selected_status else status_table.iloc[0:0]
    st.dataframe(visible, width="stretch", hide_index=True)

    _render_manual_controls(queue)

    st.subheader("Open Paper Positions & Exit Tracking")
    portfolio = load_paper_portfolio()
    columns = [
        "Symbol", "Market", "PositionQty", "AverageCost", "LastPrice", "MarketValue",
        "StopPrice", "TargetPrice", "HighestPrice", "TrailingStopPrice", "ExitReason",
        "ExitTriggeredTime", "PositionStatus",
    ]
    visible_portfolio = portfolio[
        [column for column in columns if column in portfolio.columns]
    ].copy()
    if "ExitReason" in visible_portfolio.columns:
        visible_portfolio["ExitReason"] = visible_portfolio["ExitReason"].map(
            exit_reason_label
        )
    st.dataframe(visible_portfolio, width="stretch", hide_index=True)
