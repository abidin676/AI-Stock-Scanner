import pandas as pd
from streamlit.testing.v1 import AppTest

from paper_broker import PaperBrokerConfig, load_paper_broker_config
from views.approval_queue import display_status
from views.paper_trading import DISPLAY_STATUSES, build_paper_trading_status_table


def render_paper_trading_page():
    from views.paper_trading import paper_trading_page

    paper_trading_page()


def test_paper_config_defaults_to_paper_only():
    assert PaperBrokerConfig().paper_only is True
    assert load_paper_broker_config().paper_only is True


def test_paper_trading_page_renders_without_traceback():
    app = AppTest.from_function(render_paper_trading_page, default_timeout=10).run()

    assert not app.exception
    assert [title.value for title in app.title] == ["River Alpha Paper Trading"]
    assert not app.error


def test_approval_queue_uses_current_display_statuses():
    assert display_status("PENDING_APPROVAL") == "PENDING"
    assert display_status("EXECUTED") == "FILLED"
    assert display_status("APPROVED") == "APPROVED"


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
