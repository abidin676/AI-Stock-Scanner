from datetime import datetime, timedelta

import pandas as pd
import pytest

from approval_queue import (
    ApprovalQueueError,
    approve_proposal,
    build_approval_summary,
    cancel_proposal,
    load_approval_history,
    load_approval_queue,
    ready_for_paper_broker,
    reject_proposal,
    sync_approval_queue,
    transition_proposal,
)


def risk_row(**updates):
    row = {
        "ProposalId": "RM-SET-BUYOK-BUY-20260711",
        "Symbol": "BUYOK",
        "Market": "SET",
        "SourceDecision": "BUY",
        "ProposalAction": "BUY",
        "ProposalStatus": "PENDING_APPROVAL",
        "RiskApproved": True,
        "ApprovalRequired": True,
        "EntryPrice": 10,
        "StopPrice": 9,
        "TargetPrice": 13,
        "RiskScore": 28,
        "AIConfidence": 88,
        "ProposedQty": 1000,
        "ProposedOrderValue": 10000,
        "EstimatedCommission": 15.7,
        "EstimatedSlippage": 10,
        "EstimatedTotalCost": 10025.7,
        "RiskRewardRatio": 3,
        "RiskBudget": 1000,
        "PositionSizeMethod": "risk_based_min_cap",
        "CashAfterOrder": 89974.3,
        "RejectReason": "NONE",
        "RiskWarnings": "NONE",
        "AIReason": "Seed setup",
        "AIBlockers": "",
        "ProposalPriority": 2,
        "PriorityScore": 90,
        "OpportunityScore": 80,
        "LifecycleState": "SEED",
        "ProposalTime": "2026-07-11T09:00:00",
    }
    row.update(updates)
    return row


def paths(tmp_path):
    return tmp_path / "approval_queue.csv", tmp_path / "approval_history.csv"


def test_sync_imports_pending_risk_proposal(tmp_path):
    queue_path, history_path = paths(tmp_path)
    queue, _ = sync_approval_queue(
        pd.DataFrame([risk_row()]),
        queue_path=queue_path,
        history_path=history_path,
    )

    row = queue.iloc[0]

    assert row["ProposalId"] == "RM-SET-BUYOK-BUY-20260711"
    assert row["Status"] == "PENDING_APPROVAL"
    assert row["Action"] == "BUY"
    assert row["Quantity"] == 1000
    assert row["EstimatedTotalCost"] == 10025.7


def test_duplicate_proposal_id_is_not_added_twice(tmp_path):
    queue_path, history_path = paths(tmp_path)
    proposals = pd.DataFrame([risk_row(), risk_row(AIConfidence=99)])

    queue, _ = sync_approval_queue(
        proposals,
        queue_path=queue_path,
        history_path=history_path,
    )

    assert len(queue) == 1


def test_risk_rejected_proposal_is_stored_as_rejected(tmp_path):
    queue_path, history_path = paths(tmp_path)
    queue, _ = sync_approval_queue(
        pd.DataFrame(
            [
                risk_row(
                    ProposalId="RM-SET-LOWRR-BUY-20260711",
                    Symbol="LOWRR",
                    ProposalStatus="REJECTED",
                    RiskApproved=False,
                    RejectReason="LOW_RR",
                    ProposedQty=0,
                    ProposedOrderValue=0,
                    EstimatedTotalCost=0,
                )
            ]
        ),
        queue_path=queue_path,
        history_path=history_path,
    )

    row = queue.iloc[0]

    assert row["Status"] == "REJECTED"
    assert row["RejectedReason"] == "LOW_RR"
    assert ready_for_paper_broker(queue).empty


def test_manual_approve_sets_status_and_history(tmp_path):
    queue_path, history_path = paths(tmp_path)
    sync_approval_queue(pd.DataFrame([risk_row()]), queue_path=queue_path, history_path=history_path)

    approved = approve_proposal(
        "RM-SET-BUYOK-BUY-20260711",
        approved_by="tester",
        queue_path=queue_path,
        history_path=history_path,
    )
    queue = load_approval_queue(queue_path)
    history = load_approval_history(history_path)

    assert approved["Status"] == "APPROVED"
    assert queue.iloc[0]["Status"] == "APPROVED"
    assert queue.iloc[0]["ApprovedBy"] == "tester"
    assert "APPROVED" in set(history["ToStatus"])


def test_approved_proposal_cannot_be_approved_twice(tmp_path):
    queue_path, history_path = paths(tmp_path)
    sync_approval_queue(pd.DataFrame([risk_row()]), queue_path=queue_path, history_path=history_path)
    approve_proposal("RM-SET-BUYOK-BUY-20260711", queue_path=queue_path, history_path=history_path)

    with pytest.raises(ApprovalQueueError):
        approve_proposal("RM-SET-BUYOK-BUY-20260711", queue_path=queue_path, history_path=history_path)


def test_approved_proposal_is_not_overwritten_by_new_risk_sync(tmp_path):
    queue_path, history_path = paths(tmp_path)
    sync_approval_queue(pd.DataFrame([risk_row()]), queue_path=queue_path, history_path=history_path)
    approve_proposal("RM-SET-BUYOK-BUY-20260711", queue_path=queue_path, history_path=history_path)

    sync_approval_queue(
        pd.DataFrame(
            [
                risk_row(
                    ProposedQty=9999,
                    EntryPrice=77,
                    ProposalAction="ADD",
                    ProposalStatus="REJECTED",
                    RiskApproved=False,
                    RejectReason="LOW_RR",
                )
            ]
        ),
        queue_path=queue_path,
        history_path=history_path,
    )
    queue = load_approval_queue(queue_path)
    row = queue.iloc[0]

    assert row["Status"] == "APPROVED"
    assert row["Action"] == "BUY"
    assert row["Quantity"] == 1000
    assert row["EntryPrice"] == 10
    assert row["ProposalId"] == "RM-SET-BUYOK-BUY-20260711"


def test_expired_proposal_cannot_be_approved(tmp_path):
    queue_path, history_path = paths(tmp_path)
    created = datetime(2026, 7, 11, 9, 0, 0)
    sync_approval_queue(
        pd.DataFrame([risk_row(ProposalTime=created.isoformat())]),
        queue_path=queue_path,
        history_path=history_path,
        now=created,
        expire_hours=1,
    )

    with pytest.raises(ApprovalQueueError):
        approve_proposal(
            "RM-SET-BUYOK-BUY-20260711",
            queue_path=queue_path,
            history_path=history_path,
            now=created + timedelta(hours=2),
        )

    queue = load_approval_queue(queue_path)
    assert queue.iloc[0]["Status"] == "EXPIRED"


def test_manual_reject_is_not_ready_for_paper_broker(tmp_path):
    queue_path, history_path = paths(tmp_path)
    sync_approval_queue(pd.DataFrame([risk_row()]), queue_path=queue_path, history_path=history_path)

    reject_proposal(
        "RM-SET-BUYOK-BUY-20260711",
        rejected_by="tester",
        reason="Do not chase",
        queue_path=queue_path,
        history_path=history_path,
    )
    queue = load_approval_queue(queue_path)

    assert queue.iloc[0]["Status"] == "REJECTED"
    assert queue.iloc[0]["RejectedReason"] == "Do not chase"
    assert ready_for_paper_broker(queue).empty


def test_cancelled_proposal_cannot_be_reused(tmp_path):
    queue_path, history_path = paths(tmp_path)
    sync_approval_queue(pd.DataFrame([risk_row()]), queue_path=queue_path, history_path=history_path)

    cancel_proposal(
        "RM-SET-BUYOK-BUY-20260711",
        cancelled_by="tester",
        queue_path=queue_path,
        history_path=history_path,
    )

    with pytest.raises(ApprovalQueueError):
        approve_proposal("RM-SET-BUYOK-BUY-20260711", queue_path=queue_path, history_path=history_path)

    queue = load_approval_queue(queue_path)
    assert queue.iloc[0]["Status"] == "CANCELLED"


def test_proposal_can_be_marked_executed_once_after_approval_only(tmp_path):
    queue_path, history_path = paths(tmp_path)
    sync_approval_queue(pd.DataFrame([risk_row()]), queue_path=queue_path, history_path=history_path)

    with pytest.raises(ApprovalQueueError):
        transition_proposal(
            "RM-SET-BUYOK-BUY-20260711",
            "EXECUTED",
            queue_path=queue_path,
            history_path=history_path,
        )

    approve_proposal("RM-SET-BUYOK-BUY-20260711", queue_path=queue_path, history_path=history_path)
    executed = transition_proposal(
        "RM-SET-BUYOK-BUY-20260711",
        "EXECUTED",
        changed_by="paper_broker_future",
        reason="future execution marker",
        queue_path=queue_path,
        history_path=history_path,
    )

    assert executed["Status"] == "EXECUTED"

    with pytest.raises(ApprovalQueueError):
        transition_proposal(
            "RM-SET-BUYOK-BUY-20260711",
            "EXECUTED",
            queue_path=queue_path,
            history_path=history_path,
        )


def test_ready_for_paper_broker_contains_approved_only(tmp_path):
    queue_path, history_path = paths(tmp_path)
    proposals = pd.DataFrame(
        [
            risk_row(),
            risk_row(ProposalId="RM-SET-LOWRR-BUY-20260711", Symbol="LOWRR", ProposalStatus="REJECTED", RiskApproved=False, RejectReason="LOW_RR"),
        ]
    )
    sync_approval_queue(proposals, queue_path=queue_path, history_path=history_path)
    approve_proposal("RM-SET-BUYOK-BUY-20260711", queue_path=queue_path, history_path=history_path)
    queue = load_approval_queue(queue_path)
    ready = ready_for_paper_broker(queue)

    assert len(ready) == 1
    assert ready.iloc[0]["ProposalId"] == "RM-SET-BUYOK-BUY-20260711"


def test_summary_counts_statuses(tmp_path):
    queue_path, history_path = paths(tmp_path)
    proposals = pd.DataFrame(
        [
            risk_row(),
            risk_row(ProposalId="RM-SET-LOWRR-BUY-20260711", Symbol="LOWRR", ProposalStatus="REJECTED", RiskApproved=False, RejectReason="LOW_RR"),
        ]
    )
    queue, _ = sync_approval_queue(proposals, queue_path=queue_path, history_path=history_path)
    summary = build_approval_summary(queue).iloc[0]

    assert summary["Pending"] == 1
    assert summary["Rejected"] == 1
    assert summary["Approved"] == 0
