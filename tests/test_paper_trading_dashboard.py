import pandas as pd

from views.paper_trading import DISPLAY_STATUSES, build_paper_trading_status_table


def test_status_table_exposes_all_required_lifecycle_states_and_reasons():
    queue = pd.DataFrame(
        [
            {"ProposalId": "p1", "Symbol": "A.BK", "Market": "SET", "Action": "BUY", "Status": "PENDING_APPROVAL", "ScanRunId": "s1"},
            {"ProposalId": "p2", "Symbol": "B.BK", "Market": "SET", "Action": "BUY", "Status": "APPROVED", "ScanRunId": "s1"},
            {"ProposalId": "p3", "Symbol": "C.BK", "Market": "SET", "Action": "BUY", "Status": "EXECUTED", "ScanRunId": "s1"},
            {"ProposalId": "p4", "Symbol": "D.BK", "Market": "SET", "Action": "BUY", "Status": "REJECTED", "RejectedReason": "MAX_OPEN_POSITIONS", "ScanRunId": "s1"},
            {"ProposalId": "p5", "Symbol": "E.BK", "Market": "SET", "Action": "BUY", "Status": "CANCELLED", "ScanRunId": "s1"},
            {"ProposalId": "p6", "Symbol": "F.BK", "Market": "SET", "Action": "BUY", "Status": "EXPIRED", "ScanRunId": "s1"},
        ]
    )
    table = build_paper_trading_status_table(queue, pd.DataFrame(), pd.DataFrame())

    assert set(DISPLAY_STATUSES).issubset(set(table["Status"]))
    rejected = table[table["ProposalId"] == "p4"].iloc[0]
    assert rejected["Reason"] == "MAX_OPEN_POSITIONS"


def test_hard_gate_failures_remain_visible_as_rejected_audit_rows():
    audit = pd.DataFrame(
        [
            {
                "Symbol": "OLD.BK",
                "Market": "SET",
                "ScanRunId": "scan-2",
                "AutomationType": "ENTRY",
                "ExclusionReason": "CROSS_AGE_5",
                "AuditTime": "2026-07-18T09:00:00",
            }
        ]
    )
    table = build_paper_trading_status_table(pd.DataFrame(), pd.DataFrame(), audit)

    assert len(table) == 1
    assert table.iloc[0]["Status"] == "REJECTED"
    assert table.iloc[0]["Reason"] == "CROSS_AGE_5"
