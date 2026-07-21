import pandas as pd
import pytest

from config import MAX_FRESH_CROSS_DAYS
import views.scanner as scanner_view

from views.scanner import (
    AI_ADVANCED_COLUMNS,
    AI_SIMPLE_COLUMNS,
    DEFAULT_SHOW_ADVANCED_DETAILS,
    PURCHASE_EMPTY_STATE,
    actionable_purchase_candidates,
    ai_action_label,
    ai_empty_state_message,
    ai_summary_counts,
    build_simple_dashboard_sections,
    build_buy_checklist,
    build_ai_advanced_table,
    build_ai_simple_table,
    buy_checklist_summary,
    ema_check_context,
    next_action_card,
    prepare_daily_candidates,
    scanner_results_view,
    simple_candidate_table,
    simple_buy_now_table,
    simple_pick_table,
    simple_near_buy_table,
    simple_watch_table,
    strategy_mode_cli_arg,
    summarize_reason,
)


def test_dashboard_scans_always_force_refresh(monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return type(
            "CompletedScan",
            (),
            {"returncode": 0, "stdout": "", "stderr": ""},
        )()

    monkeypatch.setattr(scanner_view.subprocess, "run", fake_run)

    scanner_view.run_scanner_from_dashboard(
        force_refresh=False,
        mode="ALL",
        workers=4,
        strategy_mode="Standard",
    )

    assert captured["command"].count("--force-refresh") == 1
    assert captured["command"][1:4] == ["scanner.py", "--mode", "ALL"]
    assert captured["kwargs"]["cwd"] == scanner_view.PROJECT_ROOT


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
        "Cross Age": "-",
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


def simple_ready_row(symbol, decision="WATCH", **overrides):
    row = ai_row(
        symbol,
        decision,
        Price=10,
        AIConfidence=80,
        StrategySignal="BUY",
        StrategySetup="Early Reversal",
        EMA9=10.2,
        EMA20=10,
        EMA50=9.5,
        EMA20Improving=True,
        EMA9AboveEMA20=True,
        DaysSinceEMA9CrossEMA20=0,
        LatestPriceDate="2026-07-17",
        CrossDate="2026-07-17",
        CrossAgeSource="days_since_bullish_ema_cross",
        PreviousEMA9=9.8,
        PreviousEMA20=10,
        BullishCrossEvent=True,
        DaysSinceEMA20SlopeTurnPositive=3,
        RSI=55,
        RVOL=1.6,
        RR=2.0,
        RiskPct=3,
        ExpansionScore=10,
        AIRiskLevel="LOW",
    )
    row.update(overrides)
    return row


def egatif_regression_row(bar_state):
    return simple_ready_row(
        "EGATIF.BK",
        "PREPARE",
        Price=6.20,
        AIConfidence=85.2,
        PriorityScore=81.23,
        OpportunityScore=76.38,
        StrategySignal="WATCH",
        StrategySetup="Early Reversal",
        LifecycleState="WATCH",
        EMA9=6.1602,
        EMA20=6.1544,
        PreviousEMA20=6.1496,
        EMA50=6.11,
        EMA20Improving=True,
        LatestPriceDate="2026-07-21",
        CrossDate="2026-07-17",
        DaysSinceEMA9CrossEMA20=2,
        BullishCrossEvent=False,
        RVOL=2.48,
        RSI=62.2,
        DistanceEMA20Pct=0.4,
        ExpansionScore=10,
        RR=2.46,
        RiskPct=1.31,
        RewardPct=3.23,
        RiskApproved=False,
        ProposalStatus="NO_PROPOSAL",
        RejectReason="QUEUE_CLASS_PREPARE",
        BarState=bar_state,
    )


def test_egatif_confirmed_bar_is_buy_with_complete_risk_levels():
    candidates = prepare_daily_candidates(
        pd.DataFrame([egatif_regression_row("CONFIRMED")])
    )
    row = candidates.iloc[0]

    assert row["FreshCrossEligible"]
    assert row["DaysSinceEMA9CrossEMA20"] == 2
    assert row["TrendFilterPassed"]
    assert row["BuyReadinessStatus"] == "READY"
    assert row["_DisplayAction"] == "BUY"
    assert row["_ActionLabel"] == "ซื้อได้"
    assert row["_MissingConditions"] == ""
    assert row["EntryPrice"] == pytest.approx(6.20)
    assert 0 < row["StopPrice"] < row["EntryPrice"]
    assert row["TargetPrice"] > row["EntryPrice"]


def test_egatif_live_bar_waits_for_close_without_losing_buy_eligibility():
    candidates = prepare_daily_candidates(
        pd.DataFrame([egatif_regression_row("LIVE")])
    )
    row = candidates.iloc[0]

    assert row["StrategyBuyEligible"]
    assert not row["BarConfirmed"]
    assert row["BuyReadinessStatus"] == "WAIT_CONFIRMATION"
    assert row["_DisplayAction"] == "WAIT_CONFIRMATION"
    assert row["_ActionLabel"] == "รอยืนยันปิดแท่ง"
    assert row["_MissingConditions"] == "รอยืนยันปิดแท่ง"
    assert row["_NextAction"] == "รอยืนยันปิดแท่ง"
    assert row["StopPrice"] > 0
    assert row["TargetPrice"] > row["EntryPrice"]


def test_simple_dashboard_buy_now_requires_buy_and_risk_passed():
    ai = pd.DataFrame(
        [
            simple_ready_row("BUY.BK", "BUY"),
            simple_ready_row("WAIT.BK", "BUY"),
        ]
    )
    risk = pd.DataFrame(
        [
            {"Symbol": "BUY.BK", "Market": "SET", "RiskApproved": True},
            {"Symbol": "WAIT.BK", "Market": "SET", "RiskApproved": False},
        ]
    )

    sections = build_simple_dashboard_sections(ai, risk)
    table = simple_buy_now_table(sections["buy_now"])

    assert table.columns.tolist() == [
        "Symbol",
        "Market",
        "Cross Age",
        "Price",
        "AI Score",
        "Reason",
    ]
    assert table["Symbol"].tolist() == ["BUY.BK"]


def test_simple_dashboard_near_buy_uses_one_missing_condition():
    ai = pd.DataFrame(
        [
            simple_ready_row(
                "KPNREIT.BK",
                "WATCH",
                RVOL=1.39,
            )
        ]
    )

    sections = build_simple_dashboard_sections(ai)
    table = simple_near_buy_table(sections["near_buy"])

    assert table.iloc[0]["Symbol"] == "KPNREIT.BK"
    assert table.iloc[0]["Missing Condition"] == "RVOL ≥ 1.5x (SET)"
    assert table.iloc[0]["Next Action"] == "รอ RVOL จาก 1.39x ให้ถึง 1.5x เพื่อเป็นซื้อได้"


def test_simple_dashboard_watch_section_limits_to_ten():
    ai = pd.DataFrame(
        [
            simple_ready_row(
                f"W{i:02d}.BK",
                "WATCH",
                RVOL=0.5,
                RSI=80,
                AIConfidence=100 - i,
            )
            for i in range(15)
        ]
    )

    sections = build_simple_dashboard_sections(ai)
    table = simple_watch_table(sections["watch"])

    assert len(table) == 10
    assert table["Symbol"].tolist() == [f"W{i:02d}.BK" for i in range(10)]


def test_simple_dashboard_deduplicates_symbol_market_across_sections():
    ai = pd.DataFrame(
        [
            simple_ready_row("DUP.BK", "WATCH", RVOL=1.0),
            simple_ready_row("DUP.BK", "BUY"),
            simple_ready_row("ONLYWATCH.BK", "WATCH", RVOL=0.5),
        ]
    )
    risk = pd.DataFrame(
        [
            {"Symbol": "DUP.BK", "Market": "SET", "RiskApproved": True},
        ]
    )

    sections = build_simple_dashboard_sections(ai, risk)
    combined = pd.concat(
        [
            sections["buy_now"],
            sections["near_buy"],
            sections["watch"],
        ],
        ignore_index=True,
    )

    assert combined["Symbol"].tolist().count("DUP.BK") == 1
    assert simple_buy_now_table(sections["buy_now"])["Symbol"].tolist() == ["DUP.BK"]


def test_daily_picks_show_top_five_per_market_with_simple_columns():
    rows = [
        simple_ready_row(
            f"SET{i}.BK",
            "BUY",
            Market="SET",
            AIConfidence=90 - i,
            RiskApproved=True,
        )
        for i in range(7)
    ] + [
        simple_ready_row(
            f"USA{i}",
            "BUY",
            Market="USA",
            AIConfidence=80 - i,
            RiskApproved=True,
        )
        for i in range(6)
    ]
    candidates = prepare_daily_candidates(pd.DataFrame(rows))

    set_table = simple_pick_table(candidates, "SET")
    usa_table = simple_pick_table(candidates, "USA")

    assert set_table.columns.tolist() == [
        "Symbol",
        "Action",
        "Cross Age",
        "Score",
        "Price",
        "Reason",
    ]
    assert len(set_table) == 5
    assert len(usa_table) == 5
    assert set_table["Symbol"].tolist() == [f"SET{i}.BK" for i in range(5)]
    assert usa_table["Symbol"].tolist() == [f"USA{i}" for i in range(5)]


def test_scanner_results_table_uses_only_simple_columns():
    candidates = prepare_daily_candidates(
        pd.DataFrame(
            [
                simple_ready_row("SIMPLE.BK", "WATCH", RSI=55, RVOL=1.2),
            ]
        )
    )

    table = simple_candidate_table(candidates)

    assert table.columns.tolist() == [
        "Symbol",
        "Market",
        "Action",
        "Cross Age",
        "Cross Status",
        "Score",
        "Price",
        "RSI",
        "RVOL",
        "Reason",
    ]
    assert table.iloc[0]["Action"] == "ใกล้ซื้อ"


def test_scanner_results_obey_canonical_ineligible_overlay_for_mo():
    candidates = prepare_daily_candidates(
        pd.DataFrame(
            [
                simple_ready_row(
                    "MO",
                    "WATCH",
                    Market="USA",
                    ExpansionScore=100,
                )
            ]
        )
    )
    audit = pd.DataFrame(
        [
            {
                "Symbol": "MO",
                "Market": "USA",
                "LatestPriceDate": "2026-07-16",
                "CrossDate": "2026-07-16",
                "CrossAge": 0,
                "CrossAgeSource": "days_since_bullish_ema_cross",
                "EMA9": 71.770458,
                "EMA20": 71.625901,
                "PreviousEMA9": 71.455573,
                "PreviousEMA20": 71.478101,
                "EMA9AboveEMA20": True,
                "BullishCrossEvent": True,
                "FreshCrossEligible": False,
                "FreshCrossStatus": "FRESH_CROSS",
                "FreshCrossStatusLabel": "Fresh Cross",
                "Rank": pd.NA,
                "IncludedInTop5": False,
                "Top5EligibilityReason": "EXTENDED",
                "ExclusionReason": "EXTENDED",
            }
        ]
    )
    fresh = pd.DataFrame(columns=["Symbol", "Market"])

    default_view = scanner_results_view(
        candidates,
        show_all=False,
        fresh_candidates=fresh,
        audit=audit,
    )
    diagnostic_view = scanner_results_view(
        candidates,
        show_all=True,
        fresh_candidates=fresh,
        audit=audit,
    )
    table = simple_candidate_table(diagnostic_view)

    assert default_view.empty
    assert diagnostic_view["Symbol"].tolist() == ["MO"]
    assert diagnostic_view.iloc[0]["_DisplayAction"] == "INELIGIBLE"
    assert table.iloc[0]["Action"] == "ไม่เข้าเกณฑ์"
    assert table.iloc[0]["Cross Status"] == "EXTENDED"
    assert table.iloc[0]["Reason"] == "EXTENDED"
    rendered_text = " ".join(table.astype(str).iloc[0].tolist())
    assert "Fresh Cross" not in rendered_text
    assert "เฝ้าดู" not in rendered_text


def test_default_purchase_ui_hides_watch_avoid_and_extended_rows():
    candidates = prepare_daily_candidates(
        pd.DataFrame(
            [
                simple_ready_row("BUY.BK", "BUY", RiskApproved=True),
                simple_ready_row("PREP.BK", "WATCH", RVOL=1.39),
                simple_ready_row("WATCH.BK", "WATCH"),
                simple_ready_row("AVOID.BK", "AVOID"),
                simple_ready_row("EXTENDED.BK", "WATCH", ExpansionScore=100),
            ]
        )
    )
    _, audit, fresh = scanner_view.rank_candidate_universe(candidates)

    default_view = scanner_results_view(
        candidates,
        show_all=False,
        fresh_candidates=fresh,
        audit=audit,
    )

    assert default_view["Symbol"].tolist() == ["BUY.BK", "PREP.BK"]
    assert set(default_view["_DisplayAction"]) == {"BUY", "PREPARE"}
    assert not set(default_view["Symbol"]) & {
        "WATCH.BK",
        "AVOID.BK",
        "EXTENDED.BK",
    }


def test_only_prepare_candidate_is_the_only_default_result():
    candidates = prepare_daily_candidates(
        pd.DataFrame(
            [
                simple_ready_row("PREP.BK", "WATCH", RVOL=1.39),
                simple_ready_row("WATCH.BK", "WATCH"),
            ]
        )
    )
    actionable = actionable_purchase_candidates(candidates)
    table = simple_candidate_table(actionable)

    assert table["Symbol"].tolist() == ["PREP.BK"]
    assert table["Action"].tolist() == ["ใกล้ซื้อ"]


def test_no_buy_or_prepare_candidates_returns_purchase_empty_state():
    candidates = prepare_daily_candidates(
        pd.DataFrame(
            [
                simple_ready_row("WATCH.BK", "WATCH"),
                simple_ready_row("AVOID.BK", "AVOID"),
            ]
        )
    )

    assert actionable_purchase_candidates(candidates).empty
    assert PURCHASE_EMPTY_STATE == (
        "วันนี้ยังไม่มีหุ้นที่พร้อมซื้อ — รอ Setup และ Volume ยืนยัน"
    )


def test_empty_purchase_universe_renders_clear_empty_state(monkeypatch):
    messages = []
    monkeypatch.setattr(scanner_view.st, "subheader", lambda *_: None)
    monkeypatch.setattr(scanner_view.st, "info", messages.append)

    scanner_view.render_todays_picks_simple(pd.DataFrame())

    assert messages == [PURCHASE_EMPTY_STATE]


def test_market_summary_uses_thai_buy_label_and_counts_real_buy(monkeypatch):
    metrics = []

    class MetricColumn:
        def metric(self, label, value):
            metrics.append((label, value))

    monkeypatch.setattr(scanner_view.st, "subheader", lambda *_: None)
    monkeypatch.setattr(
        scanner_view.st,
        "columns",
        lambda count: [MetricColumn() for _ in range(count)],
    )
    scanner_view.render_daily_market_summary(
        pd.DataFrame(
            [
                {"Market": "SET"},
                {"Market": "USA"},
            ]
        ),
        pd.DataFrame(
            [
                {"Market": "SET", "_DisplayAction": "BUY"},
                {"Market": "SET", "_DisplayAction": "PREPARE"},
            ]
        ),
        pd.DataFrame(),
    )

    metric_map = dict(metrics)
    assert "SET BUY" not in metric_map
    assert "USA BUY" not in metric_map
    assert metric_map["SET ซื้อได้"] == 1
    assert metric_map["USA ซื้อได้"] == 0


def test_top_five_never_backfills_with_non_purchase_actions():
    candidates = prepare_daily_candidates(
        pd.DataFrame(
            [
                simple_ready_row(
                    "BUY1.BK",
                    "BUY",
                    RiskApproved=True,
                    AIConfidence=70,
                ),
                simple_ready_row(
                    "BUY2.BK",
                    "BUY",
                    RiskApproved=True,
                    AIConfidence=60,
                ),
                simple_ready_row("PREP.BK", "WATCH", RVOL=1.39, AIConfidence=50),
                *[
                    simple_ready_row(
                        f"WATCH{i}.BK",
                        "WATCH",
                        AIConfidence=100 - i,
                    )
                    for i in range(5)
                ],
            ]
        )
    )

    table = simple_pick_table(candidates, "SET")

    assert table["Symbol"].tolist() == ["BUY1.BK", "BUY2.BK", "PREP.BK"]
    assert set(table["Action"]) == {"ซื้อได้", "ใกล้ซื้อ"}


@pytest.mark.parametrize(
    ("cross_age", "label", "reason"),
    [
        (0, "Today", "EMA9 เพิ่งตัด EMA20 วันนี้"),
        (1, "1D", "EMA9 ตัด EMA20 เมื่อ 1 วันก่อน"),
        (2, "2D", "EMA9 ตัด EMA20 เมื่อ 2 วันก่อน"),
    ],
)
def test_fresh_cross_ages_zero_to_two_are_eligible(
    cross_age,
    label,
    reason,
):
    candidates = prepare_daily_candidates(
        pd.DataFrame(
            [
                simple_ready_row(
                    f"AGE{cross_age}.BK",
                    DaysSinceEMA9CrossEMA20=cross_age,
                )
            ]
        )
    )

    assert bool(candidates.iloc[0]["_IsFreshEMACross"]) is True
    table = simple_candidate_table(candidates)
    assert table.iloc[0]["Cross Age"] == label
    assert table.iloc[0]["Reason"] == reason


@pytest.mark.parametrize("cross_age", [3, 5, 10])
def test_cross_age_above_configured_limit_is_not_eligible(cross_age):
    candidates = prepare_daily_candidates(
        pd.DataFrame(
            [
                simple_ready_row(
                    "STALE.BK",
                    "BUY",
                    DaysSinceEMA9CrossEMA20=cross_age,
                    RiskApproved=True,
                    RVOL=5,
                )
            ]
        )
    )

    assert bool(candidates.iloc[0]["_IsFreshEMACross"]) is False
    assert candidates.iloc[0]["_DisplayAction"] == "WATCH"
    assert simple_pick_table(candidates, "SET").empty


def test_ema9_below_ema20_is_not_eligible_even_with_recent_cross_age():
    context = ema_check_context(
        simple_ready_row(
            "BELOW.BK",
            EMA9=9.9,
            EMA20=10,
            EMA9AboveEMA20=True,
            DaysSinceEMA9CrossEMA20=1,
        )
    )

    assert context["EMA9AboveEMA20"] is False
    assert context["IsFreshEMA9Cross"] is False


def test_missing_cross_history_is_not_eligible():
    context = ema_check_context(
        simple_ready_row(
            "NOHISTORY.BK",
            DaysSinceEMA9CrossEMA20=None,
        )
    )

    assert context["DaysSinceEMACross"] is None
    assert context["IsFreshEMA9Cross"] is False


def test_kpnreit_stale_cross_is_not_pick_or_prepare_but_remains_in_all_results():
    row = simple_ready_row(
        "KPNREIT.BK",
        "WATCH",
        DaysSinceEMA9CrossEMA20=10,
        RVOL=1.39,
    )
    candidates = prepare_daily_candidates(pd.DataFrame([row]))
    sections = build_simple_dashboard_sections(pd.DataFrame([row]))

    assert simple_pick_table(candidates, "SET").empty
    assert sections["buy_now"].empty
    assert sections["near_buy"].empty
    assert candidates.iloc[0]["_DisplayAction"] == "WATCH"
    assert simple_candidate_table(candidates).iloc[0]["Symbol"] == "KPNREIT.BK"
    assert simple_candidate_table(candidates).iloc[0]["Cross Age"] == "10D"
    assert simple_candidate_table(candidates).iloc[0]["Cross Status"] == "Cross เก่า"


def test_candidates_sort_by_cross_age_then_ai_score():
    rows = [
        simple_ready_row(
            "AGE2.BK",
            "BUY",
            RiskApproved=True,
            AIConfidence=99,
            DaysSinceEMA9CrossEMA20=2,
        ),
        simple_ready_row(
            "AGE0LOW.BK",
            "BUY",
            RiskApproved=True,
            AIConfidence=70,
            DaysSinceEMA9CrossEMA20=0,
        ),
        simple_ready_row(
            "AGE1.BK",
            "BUY",
            RiskApproved=True,
            AIConfidence=100,
            DaysSinceEMA9CrossEMA20=1,
        ),
        simple_ready_row(
            "AGE0HIGH.BK",
            "BUY",
            RiskApproved=True,
            AIConfidence=90,
            DaysSinceEMA9CrossEMA20=0,
        ),
        simple_ready_row(
            "AGE3.BK",
            "BUY",
            RiskApproved=True,
            AIConfidence=100,
            DaysSinceEMA9CrossEMA20=3,
        ),
    ]

    candidates = prepare_daily_candidates(pd.DataFrame(rows))

    assert candidates["Symbol"].tolist() == [
        "AGE0HIGH.BK",
        "AGE0LOW.BK",
        "AGE1.BK",
        "AGE2.BK",
        "AGE3.BK",
    ]
    assert simple_pick_table(candidates, "SET", limit=10)["Symbol"].tolist() == [
        "AGE0HIGH.BK",
        "AGE0LOW.BK",
        "AGE1.BK",
        "AGE2.BK",
    ]


def test_fresh_cross_limit_is_configured_to_two_trading_bars():
    assert MAX_FRESH_CROSS_DAYS == 2


def test_simple_dashboard_empty_buy_state():
    ai = pd.DataFrame([simple_ready_row("WATCH.BK", "WATCH")])

    sections = build_simple_dashboard_sections(ai)
    table = simple_buy_now_table(sections["buy_now"])

    assert table.empty


def test_advanced_details_default_hidden():
    assert DEFAULT_SHOW_ADVANCED_DETAILS is False


def checklist_row(**overrides):
    row = {
        "EMA9": 11,
        "EMA20": 10,
        "DaysSinceEMA9CrossEMA20": 0,
        "EMABullishCrossToday": True,
        "LatestPriceDate": "2026-07-17",
        "CrossDate": "2026-07-17",
        "CrossAgeSource": "days_since_bullish_ema_cross",
        "PreviousEMA9": 9.8,
        "PreviousEMA20": 10,
        "BullishCrossEvent": True,
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
            DaysSinceEMA9CrossEMA20=10,
            EMABullishCrossToday=False,
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
    assert "RVOL >= 1.5x (SET)" in failed
    assert "Breakout / Pivot ยืนยัน" in failed


def test_ema_context_detects_bullish_cross_today():
    context = ema_check_context(
        {
            "EMA9": 10.5,
            "EMA20": 10,
            "DaysSinceEMA9CrossEMA20": 0,
            "LatestPriceDate": "2026-07-17",
            "CrossDate": "2026-07-17",
            "PreviousEMA9": 9.8,
            "PreviousEMA20": 10,
            "CrossAgeSource": "days_since_bullish_ema_cross",
            "BullishCrossEvent": True,
        }
    )

    assert context["EMA9AboveEMA20"] is True
    assert context["EMABullishCrossToday"] is True
    assert context["ChecklistEMAFieldUsed"] == "EMA9/EMA20"
    assert context["CrossDate"] == "2026-07-17"


def test_dashboard_never_infers_today_from_ema_above_without_cross_age():
    context = ema_check_context(
        {
            "EMA9": 10.5,
            "EMA20": 10,
            "EMA9AboveEMA20": True,
            "EMABullishCrossToday": True,
            "PreviousEMA9": 9.8,
            "PreviousEMA20": 10,
        }
    )

    assert context["EMA9AboveEMA20"] is True
    assert context["DaysSinceEMACross"] is None
    assert context["EMABullishCrossToday"] is False
    assert context["IsFreshEMA9Cross"] is False


def test_ema_context_detects_cross_one_day_ago():
    context = ema_check_context(
        {
            "EMA9": 10.5,
            "EMA20": 10,
            "DaysSinceEMA9CrossEMA20": 1,
            "LatestPriceDate": "2026-07-17",
            "CrossDate": "2026-07-16",
            "CrossAgeSource": "days_since_bullish_ema_cross",
            "BullishCrossEvent": False,
        }
    )

    assert context["EMA9AboveEMA20"] is True
    assert context["IsFreshEMA9Cross"] is True


def test_ema_context_rejects_cross_three_days_ago_still_above():
    checklist = build_buy_checklist(
        checklist_row(
            DaysSinceEMA9CrossEMA20=3,
            EMABullishCrossToday=False,
        )
    )
    by_key = {item["key"]: item["passed"] for item in checklist}

    assert by_key["ema9_above_ema20"] is True
    assert by_key["ema_cross_fresh"] is False


def test_ema_context_crossed_before_but_now_below():
    checklist = build_buy_checklist(
        checklist_row(
            EMA9=9.9,
            EMA20=10,
            DaysSinceEMA9CrossEMA20=2,
            EMABullishCrossToday=False,
        )
    )
    by_key = {item["key"]: item["passed"] for item in checklist}

    assert by_key["ema9_above_ema20"] is False
    assert by_key["ema_cross_fresh"] is False


def test_checklist_does_not_fail_current_ema_above_when_cross_history_missing():
    checklist = build_buy_checklist(
        {
            "EMA9": 10.4,
            "EMA20": 10,
            "EMA20Improving": True,
            "RSI": 55,
            "RVOL": 1.2,
            "ExpansionScore": 10,
            "RiskApproved": True,
            "RR": 2.5,
            "RiskPct": 3,
        }
    )
    by_key = {item["key"]: item["passed"] for item in checklist}
    failed_labels = {item["label"] for item in checklist if not item["passed"]}

    assert by_key["ema9_above_ema20"] is True
    assert "EMA9 อยู่เหนือ EMA20" not in failed_labels
    assert by_key["ema_cross_fresh"] is False


def test_next_action_rejects_stale_cross_before_volume_confirmation():
    action = next_action_card(
        checklist_row(
            AIDecision="WATCH",
            EMA9=10.5,
            EMA20=10,
            RVOL=1.0,
            DaysSinceEMA9CrossEMA20=10,
            EMABullishCrossToday=False,
        )
    )

    assert action["Message"] == "EMA9 Cross เกิน 2 วันทำการแล้ว"


def test_buy_checklist_missing_columns_does_not_crash():
    checklist = build_buy_checklist({})

    assert len(checklist) == 8
    assert passed_count(checklist) == 0


def test_next_action_buy_prepare_watch_exit():
    assert next_action_card(checklist_row()) == {
        "Priority": "BUY",
        "Message": "ผ่านเงื่อนไข เตรียมประเมิน Entry / Stop / Target",
    }

    prepare = next_action_card(
        checklist_row(
            AIDecision="PREPARE",
            RVOL=1.0,
        )
    )
    assert prepare["Priority"] == "PREPARE"
    assert prepare["Message"] == "รอ RVOL จาก 1.00x ให้ถึง 1.5x เพื่อเป็นซื้อได้"

    watch = next_action_card(
        checklist_row(
            AIDecision="WATCH",
            EMA9=9,
            EMA20=10,
            EMABullishCrossToday=False,
        )
    )
    assert watch["Priority"] == "WATCH"
    assert watch["Message"] == "รอ EMA9 ตัดขึ้นเหนือ EMA20"

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


def test_strategy_mode_cli_arg_maps_display_labels():
    assert strategy_mode_cli_arg("Standard") == "standard"
    assert strategy_mode_cli_arg("Early") == "early"
    assert strategy_mode_cli_arg("Pure Early") == "pure_early"
    assert strategy_mode_cli_arg("pure_early") == "pure_early"
    assert strategy_mode_cli_arg("Breakout") == "breakout"
    assert strategy_mode_cli_arg("Momentum") == "momentum"
