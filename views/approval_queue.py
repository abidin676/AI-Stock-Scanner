from pathlib import Path

import pandas as pd
import streamlit as st

from paper_trading_robot import exit_reason_label

from approval_queue import (
    APPROVAL_HISTORY_FILE,
    APPROVAL_QUEUE_FILE,
    ApprovalQueueError,
    approve_proposal,
    cancel_proposal,
    load_approval_history,
    ready_for_paper_broker,
    reject_proposal,
    sync_approval_queue,
)


DISPLAY_STATUSES = [
    "PENDING",
    "APPROVED",
    "FILLED",
    "REJECTED",
    "CANCELLED",
    "EXPIRED",
]

STATUS_LABELS = {
    "PENDING_APPROVAL": "PENDING",
    "APPROVED": "APPROVED",
    "EXECUTED": "FILLED",
    "REJECTED": "REJECTED",
    "CANCELLED": "CANCELLED",
    "EXPIRED": "EXPIRED",
}


def safe_number(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def display_status(value):
    status = str(value or "").strip().upper()
    return STATUS_LABELS.get(status, status or "UNKNOWN")


def load_queue_with_expiry():
    queue, _ = sync_approval_queue(pd.DataFrame())
    return queue


def queue_filter_options(df, column):
    if df.empty or column not in df.columns:
        return ["ALL"]

    values = sorted(
        value
        for value in df[column].dropna().astype(str).unique()
        if value.strip()
    )
    return ["ALL"] + values


def render_summary_cards(queue):
    status_counts = (
        queue.get("Status", pd.Series(dtype=str))
        .map(display_status)
        .value_counts()
        .to_dict()
    )
    first_row = st.columns(3)
    second_row = st.columns(3)
    for column, status in zip([*first_row, *second_row], DISPLAY_STATUSES):
        column.metric(status, int(status_counts.get(status, 0)))

    st.caption(
        "Approval Queue is the manual gate before Paper Trade. Approve first, "
        "then use Paper Trading for an explicit simulated Fill."
    )


def filter_queue(queue):
    queue = queue.copy()
    queue["DisplayStatus"] = queue.get("Status", pd.Series(dtype=str)).map(display_status)

    with st.expander("Filters", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        market_filter = c1.selectbox(
            "Market",
            queue_filter_options(queue, "Market"),
            key="approval_market_filter",
        )
        action_filter = c2.multiselect(
            "Action",
            queue_filter_options(queue, "Action"),
            default=["ALL"],
            key="approval_action_filter",
        )
        status_filter = c3.multiselect(
            "Status",
            ["ALL", *DISPLAY_STATUSES],
            default=["PENDING"] if "PENDING" in set(queue["DisplayStatus"]) else ["ALL"],
            key="approval_status_filter",
        )
        symbol_search = c4.text_input(
            "Search Symbol",
            value="",
            placeholder="AAPL, PTT, DUK",
            key="approval_symbol_search",
        )

    filtered = queue.copy()

    if market_filter != "ALL":
        filtered = filtered[filtered["Market"] == market_filter]

    if "ALL" not in action_filter:
        filtered = filtered[filtered["Action"].isin(action_filter)]

    if "ALL" not in status_filter:
        filtered = filtered[filtered["DisplayStatus"].isin(status_filter)]

    if symbol_search.strip():
        needles = [
            symbol.strip().upper()
            for symbol in symbol_search.split(",")
            if symbol.strip()
        ]
        filtered = filtered[
            filtered["Symbol"]
            .astype(str)
            .str.upper()
            .apply(lambda value: any(needle in value for needle in needles))
        ]

    return filtered


def render_queue_table(filtered):
    columns = [
        "ProposalId",
        "Symbol",
        "Market",
        "Action",
        "Quantity",
        "ProposedOrderValue",
        "RiskScore",
        "AIConfidence",
        "DisplayStatus",
        "CreatedTime",
        "ExpireTime",
    ]
    display = filtered[[column for column in columns if column in filtered.columns]].copy()
    display = display.rename(
        columns={
            "ProposedOrderValue": "Order Value",
            "RiskScore": "Risk Score",
            "AIConfidence": "AI Confidence",
            "DisplayStatus": "Status",
            "CreatedTime": "Created Time",
            "ExpireTime": "Expire Time",
        }
    )

    st.markdown("**Proposal Queue**")
    st.dataframe(
        display,
        width="stretch",
        hide_index=True,
    )


def render_metric_grid(row):
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Action", row["Action"])
    c2.metric("Status", display_status(row["Status"]))
    c3.metric("Qty", f"{safe_number(row['Quantity']):,.2f}")
    c4.metric("Entry", f"{safe_number(row['EntryPrice']):,.2f}")
    c5.metric("Stop", f"{safe_number(row['StopPrice']):,.2f}")
    c6.metric("Target", f"{safe_number(row['TargetPrice']):,.2f}")


def render_detail_tabs(row):
    overview, ai_tab, risk_tab, sizing_tab, cost_tab, history_tab = st.tabs(
        [
            "Overview",
            "AI Decision",
            "Risk Analysis",
            "Position Sizing",
            "Costs",
            "History",
        ]
    )

    with overview:
        render_metric_grid(row)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Risk Score", f"{safe_number(row['RiskScore']):.1f}")
        c2.metric("AI Confidence", f"{safe_number(row['AIConfidence']):.1f}")
        c3.metric("RR", f"{safe_number(row['RiskRewardRatio']):.2f}")
        c4.metric("Order Value", f"{safe_number(row['ProposedOrderValue']):,.2f}")
        st.write(f"Created: {row['CreatedTime']}")
        st.write(f"Expires: {row['ExpireTime']}")
        if str(row.get("AutomationType", "")).upper() == "EXIT":
            st.write(
                f"Exit reason: {exit_reason_label(row.get('AutomationReason', '')) or 'N/A'}"
            )

    with ai_tab:
        c1, c2, c3 = st.columns(3)
        c1.metric("AI Decision", row["SourceDecision"])
        c2.metric("Priority Score", f"{safe_number(row['PriorityScore']):.1f}")
        c3.metric("Opportunity Score", f"{safe_number(row['OpportunityScore']):.1f}")
        st.markdown("**AI Reason**")
        st.write(row["AIReason"] or "No AI reason recorded.")
        st.markdown("**AI Blockers**")
        st.write(row["AIBlockers"] or "None")

    with risk_tab:
        c1, c2, c3 = st.columns(3)
        c1.metric("Risk Level", row["RiskLevel"])
        c2.metric("Risk Score", f"{safe_number(row['RiskScore']):.1f}")
        c3.metric("RR", f"{safe_number(row['RiskRewardRatio']):.2f}")
        st.markdown("**Risk Manager Reason**")
        st.write(row["RiskManagerReason"] or "NONE")
        st.markdown("**Risk Manager Warnings**")
        st.write(row["RiskManagerWarnings"] or "NONE")

    with sizing_tab:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Method", row["PositionSizeMethod"] or "N/A")
        c2.metric("Risk Budget", f"{safe_number(row['RiskBudget']):,.2f}")
        c3.metric("Quantity", f"{safe_number(row['Quantity']):,.2f}")
        c4.metric("Cash After", f"{safe_number(row['CashAfterOrder']):,.2f}")

    with cost_tab:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Order Value", f"{safe_number(row['ProposedOrderValue']):,.2f}")
        c2.metric("Commission", f"{safe_number(row['EstimatedCommission']):,.2f}")
        c3.metric("Slippage", f"{safe_number(row['EstimatedSlippage']):,.2f}")
        c4.metric("Total Cost", f"{safe_number(row['EstimatedTotalCost']):,.2f}")

    with history_tab:
        history = load_approval_history()
        history = history[history["ProposalId"] == row["ProposalId"]]
        if history.empty:
            st.info("No history found for this proposal.")
        else:
            st.dataframe(history, width="stretch", hide_index=True)


def render_manual_actions(row):
    st.markdown("**Manual Approval Gate**")

    if row["Status"] != "PENDING_APPROVAL":
        st.info("Only pending proposals can be approved, rejected, or cancelled.")
        return

    st.warning(
        "Approve changes the proposal to APPROVED and makes it available for "
        "manual Fill in Paper Trading. It never fills automatically."
    )

    approved_by = st.text_input(
        "Approved / Changed By",
        value="manual",
        key=f"approval_actor_{row['ProposalId']}",
    )
    reject_reason = st.text_input(
        "Reject / Cancel Reason",
        value="Manual review",
        key=f"approval_reason_{row['ProposalId']}",
    )

    c1, c2, c3 = st.columns(3)

    if c1.button("Approve", key=f"approve_{row['ProposalId']}"):
        try:
            approve_proposal(row["ProposalId"], approved_by=approved_by)
            st.success("Proposal approved. Open Paper Trading to review and Fill the simulated order.")
            st.rerun()
        except ApprovalQueueError as exc:
            st.error(str(exc))

    if c2.button("Reject", key=f"reject_{row['ProposalId']}"):
        try:
            reject_proposal(
                row["ProposalId"],
                rejected_by=approved_by,
                reason=reject_reason,
            )
            st.success("Proposal rejected.")
            st.rerun()
        except ApprovalQueueError as exc:
            st.error(str(exc))

    if c3.button("Cancel", key=f"cancel_{row['ProposalId']}"):
        try:
            cancel_proposal(
                row["ProposalId"],
                cancelled_by=approved_by,
                reason=reject_reason,
            )
            st.success("Proposal cancelled.")
            st.rerun()
        except ApprovalQueueError as exc:
            st.error(str(exc))


def render_ready_preview(queue):
    ready = ready_for_paper_broker(queue)

    with st.expander("APPROVED — Ready For Paper Trading Fill", expanded=False):
        st.caption(
            "Only APPROVED proposals are shown. Fill remains a separate explicit "
            "action on the Paper Trading page."
        )

        if ready.empty:
            st.info("No APPROVED proposals are waiting for a Paper Trading Fill.")
            return

        columns = [
            "ProposalId",
            "Symbol",
            "Market",
            "Action",
            "Quantity",
            "ProposedOrderValue",
            "Status",
            "ApprovedBy",
            "ApprovedTime",
        ]
        display = ready[[column for column in columns if column in ready.columns]].copy()
        if "Status" in display.columns:
            display["Status"] = display["Status"].map(display_status)
        st.dataframe(display, width="stretch", hide_index=True)


def approval_queue_page():
    st.title("Approval Queue")
    st.caption("Manual approval gate between Risk Manager and SET Paper Trading.")
    st.warning(
        "PAPER TRADING ONLY — Approve here, then Fill explicitly on the Paper Trading page. "
        "There is no real broker connection and no broker API call."
    )

    queue = load_queue_with_expiry()
    render_summary_cards(queue)

    if queue.empty:
        st.info("No approval queue found yet. Run Scanner after Risk Manager creates proposals.")
        return

    filtered = filter_queue(queue)

    if filtered.empty:
        st.info("No proposals found for current filters.")
    else:
        render_queue_table(filtered)

        labels = [
            f"{row.ProposalId} | {row.Symbol} | {row.Action} | {display_status(row.Status)}"
            for row in filtered.itertuples()
        ]
        selected = st.selectbox(
            "Proposal Detail",
            labels,
            key="approval_detail_select",
        )
        row = filtered.iloc[labels.index(selected)].to_dict()

        render_detail_tabs(row)
        render_manual_actions(row)

    render_ready_preview(queue)

    queue_bytes = queue.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Export Queue CSV",
        data=queue_bytes,
        file_name="approval_queue.csv",
        mime="text/csv",
    )
    st.caption(f"Queue file: {Path(APPROVAL_QUEUE_FILE)}")
    st.caption(f"History file: {Path(APPROVAL_HISTORY_FILE)}")
