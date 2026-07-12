import pandas as pd

from views.scanner import (
    AI_ADVANCED_COLUMNS,
    AI_SIMPLE_COLUMNS,
    ai_action_label,
    ai_empty_state_message,
    ai_summary_counts,
    build_ai_advanced_table,
    build_ai_simple_table,
)


def ai_row(symbol, decision, **overrides):
    row = {
        "Symbol": symbol,
        "Market": "SET",
        "AIDecision": decision,
        "AIConfidence": 70,
        "AIConviction": "MEDIUM",
        "LifecycleState": "SEED",
        "PriorityScore": 80,
        "OpportunityScore": 60,
        "AIRiskLevel": "LOW",
        "AIReason": "Ready to buy after approval",
        "AIReviewPriority": 3,
    }
    row.update(overrides)
    return row


def test_ai_status_label_mapping():
    assert ai_action_label("BUY") == "🟢 ซื้อได้"
    assert ai_action_label("PREPARE") == "🟡 ใกล้ซื้อ"
    assert ai_action_label("WATCH") == "👀 เฝ้าดู"
    assert ai_action_label("HOLD") == "🔵 ถือ"
    assert ai_action_label("EXIT") == "🔴 ขาย"
    assert ai_action_label("NONE") == "⚪ ยังไม่ทำอะไร"
    assert ai_action_label("SKIP") == "⚪ ยังไม่ทำอะไร"


def test_simple_table_has_only_five_user_facing_columns():
    data = pd.DataFrame(
        [
            ai_row("BUY.BK", "BUY"),
            ai_row("WATCH.BK", "WATCH", AIReason="Need volume confirmation"),
        ]
    )

    simple = build_ai_simple_table(data)

    assert simple.columns.tolist() == AI_SIMPLE_COLUMNS
    assert simple.iloc[0].to_dict() == {
        "Symbol": "BUY.BK",
        "Action": "🟢 ซื้อได้",
        "AI Score": 70,
        "Risk": "LOW",
        "Reason": "พร้อมเข้าซื้อ",
    }


def test_advanced_table_keeps_original_technical_columns():
    data = pd.DataFrame([ai_row("ADV.BK", "PREPARE")])

    advanced = build_ai_advanced_table(data)

    assert advanced.columns.tolist() == AI_ADVANCED_COLUMNS
    assert advanced.iloc[0]["AIDecision"] == "PREPARE"
    assert advanced.iloc[0]["PriorityScore"] == 80
    assert advanced.iloc[0]["OpportunityScore"] == 60


def test_simple_queue_uses_action_group_order():
    data = pd.DataFrame(
        [
            ai_row("WATCH.BK", "WATCH"),
            ai_row("HOLD.BK", "HOLD"),
            ai_row("EXIT.BK", "EXIT"),
            ai_row("PREP.BK", "PREPARE"),
            ai_row("BUY.BK", "BUY"),
        ]
    )

    simple = build_ai_simple_table(data, show_all_watch=True)

    assert simple["Symbol"].tolist() == [
        "BUY.BK",
        "PREP.BK",
        "EXIT.BK",
        "HOLD.BK",
        "WATCH.BK",
    ]


def test_watch_default_limit_is_twenty():
    data = pd.DataFrame(
        [
            ai_row(f"W{i:02d}.BK", "WATCH", AIConfidence=100 - i)
            for i in range(25)
        ]
    )

    simple = build_ai_simple_table(data)

    assert len(simple) == 20
    assert simple["Symbol"].tolist() == [f"W{i:02d}.BK" for i in range(20)]


def test_show_all_watch_candidates_returns_all_watch_rows():
    data = pd.DataFrame(
        [
            ai_row(f"W{i:02d}.BK", "WATCH", AIConfidence=100 - i)
            for i in range(25)
        ]
    )

    simple = build_ai_simple_table(data, show_all_watch=True)

    assert len(simple) == 25


def test_empty_dataframe_does_not_crash():
    simple = build_ai_simple_table(pd.DataFrame())
    advanced = build_ai_advanced_table(pd.DataFrame())

    assert simple.columns.tolist() == AI_SIMPLE_COLUMNS
    assert simple.empty
    assert advanced.columns.tolist() == AI_ADVANCED_COLUMNS
    assert advanced.empty


def test_missing_optional_columns_do_not_crash():
    data = pd.DataFrame(
        [
            {
                "Symbol": "MISS.BK",
                "AIDecision": "WATCH",
            }
        ]
    )

    simple = build_ai_simple_table(data)
    advanced = build_ai_advanced_table(data)

    assert simple.iloc[0]["Symbol"] == "MISS.BK"
    assert simple.iloc[0]["Risk"] == "UNKNOWN"
    assert advanced.iloc[0]["Market"] == ""
    assert advanced.iloc[0]["AIConfidence"] == 0


def test_buy_zero_empty_state_message_mentions_prepare_count():
    counts = ai_summary_counts(
        pd.DataFrame(
            [
                ai_row("P1.BK", "PREPARE"),
                ai_row("P2.BK", "PREPARE"),
                ai_row("W1.BK", "WATCH"),
            ]
        )
    )

    message = ai_empty_state_message(counts)

    assert "วันนี้ยังไม่มีหุ้นที่ AI แนะนำให้ซื้อ" in message
    assert "มี 2 ตัวใกล้เข้าเงื่อนไขซื้อ" in message


def test_original_dataframe_is_not_mutated_by_dashboard_helpers():
    original = pd.DataFrame([ai_row("RAW.BK", "BUY")])
    before_columns = original.columns.tolist()
    before_data = original.copy(deep=True)

    build_ai_simple_table(original)
    build_ai_advanced_table(original)

    assert original.columns.tolist() == before_columns
    pd.testing.assert_frame_equal(original, before_data)
