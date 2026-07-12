import pandas as pd

from views.scanner import (
    AI_ADVANCED_COLUMNS,
    AI_SIMPLE_COLUMNS,
    ai_action_label,
    ai_empty_state_message,
    ai_summary_counts,
    build_buy_checklist,
    build_ai_advanced_table,
    build_ai_simple_table,
    buy_checklist_summary,
    next_action_card,
    summarize_reason,
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


def checklist_row(**overrides):
    row = {
        "EMA9": 11,
        "EMA20": 10,
        "EMA50": 12,
        "EMA200": 9,
        "EMA20Improving": True,
        "RSI": 55,
        "RVOL": 1.7,
        "PocketPivot": True,
        "ExpansionScore": 10,
        "RiskApproved": True,
        "RR": 2.5,
        "RiskPct": 3,
        "AIDecision": "BUY",
    }
    row.update(overrides)
    return row


def passed_count(items):
    return sum(1 for item in items if item["passed"])


def test_summarize_reason_mapping():
    assert summarize_reason({"AIReason": "Need Breakout confirmation"}) == "รอ Breakout"
    assert summarize_reason({"AIReason": "Need Volume confirmation"}) == "รอ Volume"
    assert summarize_reason({"AIReason": "Risk is still elevated"}) == "Risk ยังไม่ผ่าน"
    assert summarize_reason({"AIReason": "Scanner status is SKIP"}) == "สถานะ Scanner เป็น SKIP"
    assert summarize_reason({"AIReason": "Exit because setup invalidated"}) == "แนวโน้มเสีย"
    assert summarize_reason({"AIReason": "LOW_RR blocker"}) == "Risk/Reward ยังไม่เหมาะ"
    assert summarize_reason({"AIReason": "EMA confirmation missing"}) == "EMA ยังไม่ยืนยัน"
    assert summarize_reason({"AIReason": "WATCH context accumulation"}) == "ยังอยู่ช่วงสะสม"


def test_summarize_reason_unknown_truncates_to_sixty_chars():
    reason = "x" * 100

    summary = summarize_reason({"AIReason": reason})

    assert len(summary) <= 60
    assert summary.endswith("...")


def test_buy_checklist_all_true():
    checklist = build_buy_checklist(checklist_row())

    assert passed_count(checklist) == 8
    assert buy_checklist_summary(checklist) == "ผ่านแล้ว 8/8 เงื่อนไข"


def test_buy_checklist_all_false():
    checklist = build_buy_checklist(
        checklist_row(
            EMA9=9,
            EMA20=10,
            EMA50=8,
            EMA200=9,
            EMA20Improving=False,
            DaysSinceEMA20SlopeTurnPositive=0,
            RSI=75,
            RVOL=0.7,
            PocketPivot=False,
            StrategySetup="Base forming",
            ExpansionScore=90,
            RiskApproved=False,
            RR=0.5,
            RiskPct=12,
        )
    )

    assert passed_count(checklist) == 0
    assert buy_checklist_summary(checklist) == "ผ่านแล้ว 0/8 เงื่อนไข"


def test_buy_checklist_mixed_shows_missing_volume_and_breakout():
    checklist = build_buy_checklist(
        checklist_row(
            RVOL=1.1,
            PocketPivot=False,
            StrategySetup="Seed base",
        )
    )
    failed = {
        item["label"]
        for item in checklist
        if not item["passed"]
    }

    assert passed_count(checklist) == 6
    assert "RVOL >= 1.5x" in failed
    assert "Breakout / Pivot ยืนยัน" in failed


def test_buy_checklist_missing_columns_does_not_crash():
    checklist = build_buy_checklist({})

    assert len(checklist) == 8
    assert passed_count(checklist) == 0


def test_next_action_buy_prepare_watch_exit():
    assert next_action_card(checklist_row()) == {
        "Priority": "BUY",
        "Message": "พร้อมเข้าซื้อ",
    }

    prepare = next_action_card(
        checklist_row(
            AIDecision="PREPARE",
            RVOL=1.0,
        )
    )
    assert prepare["Priority"] == "PREPARE"
    assert prepare["Message"] == "รอ Volume มากกว่า 1.5x"

    watch = next_action_card(
        checklist_row(
            AIDecision="WATCH",
            EMA9=9,
            EMA20=10,
        )
    )
    assert watch["Priority"] == "WATCH"
    assert watch["Message"] == "รอ EMA9 ตัด EMA20"

    exit_action = next_action_card(
        checklist_row(
            AIDecision="EXIT",
            AIBlockers="BELOW_STOP",
        )
    )
    assert exit_action == {
        "Priority": "EXIT",
        "Message": "แนวโน้มเสียแล้ว",
    }


def test_next_action_uses_recommended_action_when_priority_action_is_badge():
    action = next_action_card(
        checklist_row(
            AIDecision="",
            PriorityAction="High Priority",
            RecommendedAction="Buy",
        )
    )

    assert action["Priority"] == "BUY"


def test_new_ui_helpers_do_not_mutate_original_dataframe():
    original = pd.DataFrame([checklist_row(Symbol="SAFE.BK")])
    before = original.copy(deep=True)
    row = original.iloc[0]

    build_buy_checklist(row)
    next_action_card(row)
    summarize_reason(row)

    pd.testing.assert_frame_equal(original, before)
