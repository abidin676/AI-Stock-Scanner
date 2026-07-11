from pathlib import Path

import pandas as pd
import streamlit as st

from approval_queue import (
    APPROVAL_HISTORY_FILE,
    APPROVAL_QUEUE_FILE,
    ApprovalQueueError,
    approve_proposal,
    build_approval_summary,
    cancel_proposal,
    load_approval_history,
    ready_for_paper_broker,
    reject_proposal,
    sync_approval_queue,
)


def safe_number(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


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
    summary = build_approval_summary(queue)
    row = summary.iloc[0] if not summary.empty else {}

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Pending", int(safe_number(row.get("Pending", 0))))
    c2.metric("Approved", int(safe_number(row.get("Approved", 0))))
    c3.metric("Rejected", int(safe_number(row.get("Rejected", 0))))
    c4.metric("Expired", int(safe_number(row.get("Expired", 0))))
    c5.metric("Cancelled", int(safe_number(row.get("Cancelled", 0))))

    st.caption(
        "Approved proposals are only staged for future Paper Broker integration. "
        "No order is executed in this phase."
    )


def filter_queue(queue):
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
            queue_filter_options(queue, "Status"),
            default=["PENDING_APPROVAL"] if "PENDING_APPROVAL" in queue_filter_options(queue, "Status") else ["ALL"],
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
        filtered = filtered[filtered["Status"].isin(status_filter)]

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
        "Status",
        "CreatedTime",
        "ExpireTime",
    ]
    display = filtered[[column for column in columns if column in filtered.columns]].copy()
    display = display.rename(
        columns={
            "ProposedOrderValue": "Order Value",
            "RiskScore": "Risk Score",
            "AIConfidence": "AI Confidence",
            "CreatedTime": "Created Time",
            "ExpireTime": "Expire Time",
        }
    )

    st.markdown("**Proposal Queue**")
    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
    )


def render_metric_grid(row):
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Action", row["Action"])
    c2.metric("Status", row["Status"])
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
            st.dataframe(history, use_container_width=True, hide_index=True)


def render_manual_actions(row):
    st.markdown("**Manual Approval Gate**")

    if row["Status"] != "PENDING_APPROVAL":
        st.info("Only pending proposals can be approved, rejected, or cancelled.")
        return

    st.warning(
        "Approval only changes queue status. "
        "No broker API call and no paper trade execution will run."
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
            st.success("Proposal approved. It is now ready for future Paper Broker integration.")
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

    with st.expander("Ready For Future Paper Broker", expanded=False):
        st.caption(
            "Preview only. Rejected, expired, cancelled, and pending proposals are excluded. "
            "No order execution exists in this phase."
        )

        if ready.empty:
            st.info("No approved proposals ready for future Paper Broker integration.")
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
        st.dataframe(
            ready[[column for column in columns if column in ready.columns]],
            use_container_width=True,
            hide_index=True,
        )


def approval_queue_page():
    st.title("Approval Queue")
    st.caption("Manual control layer between Risk Manager and future Paper Broker.")
    st.warning(
        "Phase 1 is approval-only. There is no broker connection, no API call, "
        "and no paper trade execution."
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
            f"{row.ProposalId} | {row.Symbol} | {row.Action} | {row.Status}"
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
