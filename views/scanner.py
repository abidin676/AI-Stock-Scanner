from pathlib import Path
from datetime import datetime
import html
import subprocess
import sys

import pandas as pd
import streamlit as st

from config import MAX_WORKERS
from data import PRICE_CACHE_DIR
from market_quality import (
    calculate_market_quality,
    latest_market_quality_with_trend,
    load_market_quality,
)
from strategy_lifecycle import get_state_transitions
from watchlist import add_to_watchlist


RESULT_FILE = Path("output") / "scanner_results.xlsx"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCAN_MODE_OPTIONS = [
    "ALL",
    "SET50",
    "SET100",
    "SET All",
    "USA Watchlist",
    "USA All",
]
STRATEGY_MODE_OPTIONS = [
    "Standard",
    "Early",
    "Breakout",
    "Momentum",
]
SIGNAL_ORDER = {
    "BUY": 0,
    "WATCH": 1,
    "EARLY": 2,
    "EXTENDED": 3,
    "SKIP": 4,
    "OTHER": 5,
}
LIFECYCLE_STATES = [
    "ALL",
    "EARLY",
    "BREAKOUT",
    "MOMENTUM",
    "EXTENDED",
    "WATCH",
    "SKIP",
    "UNKNOWN",
]
DISPLAY_COLUMNS = [
    "Symbol",
    "Market",
    "LifecycleState",
    "PreviousLifecycleState",
    "DaysInState",
    "StateChanged",
    "StrategyMode",
    "StrategySignal",
    "StrategySetup",
    "StrategyScore",
    "Signal",
    "Setup",
    "Score",
    "Price",
    "RSI",
    "RVOL",
]
ROW_COLORS = {
    "BUY": "#dcfce7",
    "WATCH": "#dbeafe",
    "EARLY": "#fef9c3",
    "EXTENDED": "#ffedd5",
    "SKIP": "#f3f4f6",
}
LIFECYCLE_ROW_COLORS = {
    "EARLY": "#dcfce7",
    "BREAKOUT": "#ffedd5",
    "MOMENTUM": "#dbeafe",
    "EXTENDED": "#fed7aa",
    "WATCH": "#e0f2fe",
    "SKIP": "#f3f4f6",
    "UNKNOWN": "#f9fafb",
}
QUALITY_DISPLAY_COLUMNS = [
    "Market",
    "StrategyMode",
    "QualityScore",
    "QualityLabel",
    "Trend",
    "TotalStocks",
    "BuyCount",
    "AvgBuyScore",
    "BreakoutCount",
    "ScanTimeSeconds",
    "LastScanTime",
]


def signal_group(signal):

    signal = str(signal)

    if "BUY" in signal:
        return "BUY"

    if "WATCH" in signal:
        return "WATCH"

    if "EARLY" in signal:
        return "EARLY"

    if "EXTENDED" in signal:
        return "EXTENDED"

    if "SKIP" in signal:
        return "SKIP"

    return "OTHER"


def ensure_strategy_columns(df):

    data = df.copy()

    if "Signal" not in data.columns:
        data["Signal"] = ""

    if "Setup" not in data.columns:
        data["Setup"] = ""

    if "Score" not in data.columns:
        data["Score"] = 0

    if "StrategyMode" not in data.columns:
        data["StrategyMode"] = "Standard"

    if "StrategySignal" not in data.columns:
        data["StrategySignal"] = data["Signal"]

    if "StrategySetup" not in data.columns:
        data["StrategySetup"] = data["Setup"]

    if "StrategyScore" not in data.columns:
        data["StrategyScore"] = data["Score"]

    data["StrategyScore"] = pd.to_numeric(
        data["StrategyScore"],
        errors="coerce",
    ).fillna(0)
    data["Score"] = pd.to_numeric(
        data["Score"],
        errors="coerce",
    ).fillna(0)

    return data


def ensure_lifecycle_columns(df):

    data = df.copy()

    if "LifecycleState" not in data.columns:
        data["LifecycleState"] = "UNKNOWN"

    if "PreviousLifecycleState" not in data.columns:
        data["PreviousLifecycleState"] = "UNKNOWN"

    if "DaysInState" not in data.columns:
        data["DaysInState"] = 0

    if "StateChanged" not in data.columns:
        data["StateChanged"] = False

    data["LifecycleState"] = (
        data["LifecycleState"]
        .fillna("UNKNOWN")
        .astype(str)
        .str.upper()
        .replace("", "UNKNOWN")
    )
    data["PreviousLifecycleState"] = (
        data["PreviousLifecycleState"]
        .fillna("UNKNOWN")
        .astype(str)
        .str.upper()
        .replace("", "UNKNOWN")
    )
    data["DaysInState"] = pd.to_numeric(
        data["DaysInState"],
        errors="coerce",
    ).fillna(0).astype(int)
    data["StateChanged"] = data["StateChanged"].apply(
        lambda value: str(value).strip().upper()
        in {
            "TRUE",
            "1",
            "YES",
            "Y",
        }
        if not isinstance(value, bool)
        else value
    )

    return data


def prepare_data(df):

    df = ensure_strategy_columns(df)
    df = ensure_lifecycle_columns(df)
    df["_signal_group"] = df["StrategySignal"].apply(signal_group)
    df["_signal_rank"] = df["_signal_group"].map(
        SIGNAL_ORDER
    ).fillna(
        SIGNAL_ORDER["OTHER"]
    )

    return df


def sort_results(df):

    return df.sort_values(
        [
            "_signal_rank",
            "StrategyScore",
            "RVOL",
            "RSI",
        ],
        ascending=[
            True,
            False,
            False,
            True,
        ],
    )


def visible_columns(df):

    return [
        column
        for column in DISPLAY_COLUMNS
        if column in df.columns
    ]


def safe_number(value):

    if pd.isna(value):
        return 0.0

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def format_quality_number(value, suffix=""):

    return f"{safe_number(value):,.2f}{suffix}"


def latest_quality_from_results(df, last_scan):

    quality = calculate_market_quality(
        df,
        scan_time_seconds={},
        last_scan_time=last_scan,
    )
    quality["Trend"] = "N/A"

    return quality


def load_quality_for_dashboard(df, last_scan):

    history = load_market_quality()

    if history.empty:
        return latest_quality_from_results(
            df,
            last_scan,
        )

    latest = latest_market_quality_with_trend(history)

    if latest.empty:
        return latest_quality_from_results(
            df,
            last_scan,
        )

    current_mode = current_strategy_mode(df)
    latest = latest[
        latest["StrategyMode"].fillna("Standard").astype(str)
        == current_mode
    ]

    if latest.empty:
        return latest_quality_from_results(
            df,
            last_scan,
        )

    return latest


def current_strategy_mode(df):

    if "StrategyMode" not in df.columns or df.empty:
        return "Standard"

    modes = (
        df["StrategyMode"]
        .fillna("Standard")
        .astype(str)
        .replace("", "Standard")
    )

    if modes.empty:
        return "Standard"

    return modes.mode().iloc[0]


def watchlist_label(row):

    return (
        f"{row['Symbol']} | {row['Market']} | "
        f"{row['StrategySignal']} | {row['StrategySetup']} | "
        f"Score {row['StrategyScore']}"
    )


def first_existing_number(row, columns):

    for column in columns:
        if column in row:
            return safe_number(row.get(column, 0.0))

    return 0.0


def selected_candidate_row(candidates, selected):

    symbol, market = [
        part.strip()
        for part in selected.split("|")[:2]
    ]

    return candidates[
        (candidates["Symbol"] == symbol)
        &
        (candidates["Market"] == market)
    ].iloc[0]


def apply_filters(
    df,
    market_filter,
    signal_filter,
    symbol_search,
    lifecycle_filter=None,
    state_changed_only=False,
):

    data = df.copy()

    if market_filter != "ALL":
        data = data[data["Market"] == market_filter]

    if "ALL" not in signal_filter:
        data = data[
            data["_signal_group"].isin(signal_filter)
        ]

    lifecycle_filter = lifecycle_filter or [
        "ALL",
    ]

    if "ALL" not in lifecycle_filter:
        data = data[
            data["LifecycleState"].isin(lifecycle_filter)
        ]

    if state_changed_only:
        data = data[data["StateChanged"]]

    symbol_search = symbol_search.strip().upper()

    if symbol_search:
        data = data[
            data["Symbol"].astype(str).str.upper().str.contains(
                symbol_search,
                regex=False,
            )
        ]

    return sort_results(data)


def render_lifecycle_section(df):

    st.subheader("Strategy Lifecycle")

    changed = df[df["StateChanged"]]
    metric_cols = st.columns(5)

    metrics = [
        (
            "New Early",
            int(
                (
                    (changed["LifecycleState"] == "EARLY")
                ).sum()
            ),
        ),
        (
            "New Breakout",
            int(
                (
                    (changed["LifecycleState"] == "BREAKOUT")
                ).sum()
            ),
        ),
        (
            "New Momentum",
            int(
                (
                    (changed["LifecycleState"] == "MOMENTUM")
                ).sum()
            ),
        ),
        (
            "Extended Count",
            int(
                (
                    df["LifecycleState"] == "EXTENDED"
                ).sum()
            ),
        ),
        (
            "State Changes Today",
            int(len(changed)),
        ),
    ]

    for column, (label, value) in zip(metric_cols, metrics):
        column.metric(
            label,
            value,
        )

    transitions = get_state_transitions(
        limit=25,
    )

    with st.expander("Recent State Transitions"):
        if transitions.empty:
            st.info("No recent state transitions")
        else:
            st.dataframe(
                transitions,
                use_container_width=True,
                hide_index=True,
            )


def render_market_quality_cards(df, last_scan):

    quality = load_quality_for_dashboard(
        df,
        last_scan,
    )

    st.subheader("Market Quality")

    cards = st.columns(2)

    for index, market in enumerate(("SET", "USA")):
        row = quality[
            quality["Market"].astype(str).str.upper() == market
        ]

        with cards[index]:
            if row.empty:
                st.info(f"No {market} market quality")
                continue

            data = row.iloc[0]
            trend = data.get(
                "Trend",
                "N/A",
            )
            label = data.get(
                "QualityLabel",
                "",
            )

            st.metric(
                f"{market} Quality Score",
                format_quality_number(
                    data.get(
                        "QualityScore",
                        0,
                    )
                ),
                f"Trend {trend}",
            )
            st.caption(label)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric(
                "BUY Count",
                int(
                    safe_number(
                        data.get(
                            "BuyCount",
                            0,
                        )
                    )
                ),
            )
            c2.metric(
                "Avg BUY Score",
                format_quality_number(
                    data.get(
                        "AvgBuyScore",
                        0,
                    )
                ),
            )
            c3.metric(
                "Breakout Count",
                int(
                    safe_number(
                        data.get(
                            "BreakoutCount",
                            0,
                        )
                    )
                ),
            )
            c4.metric(
                "Scan Time",
                format_quality_number(
                    data.get(
                        "ScanTimeSeconds",
                        0,
                    ),
                    "s",
                ),
            )

    with st.expander("Market Quality Details"):
        display_columns = [
            column
            for column in QUALITY_DISPLAY_COLUMNS
            if column in quality.columns
        ]
        st.dataframe(
            quality[display_columns],
            use_container_width=True,
            hide_index=True,
        )


def render_table(df):

    columns = visible_columns(df)

    header = "".join(
        f"<th>{html.escape(column)}</th>"
        for column in columns
    )

    rows = []

    for _, row in df.iterrows():

        lifecycle_state = str(
            row.get(
                "LifecycleState",
                "",
            )
        ).upper()
        group = row.get(
            "_signal_group",
            "OTHER",
        )
        background = LIFECYCLE_ROW_COLORS.get(
            lifecycle_state,
            ROW_COLORS.get(
                group,
                "#ffffff",
            ),
        )

        cell_style = (
            f"background-color: {background}; "
            "color: #111827 !important; "
            "font-weight: 700; "
            "padding: 9px 12px; "
            "border-top: 1px solid rgba(17, 24, 39, 0.12); "
            "white-space: nowrap;"
        )

        cells = "".join(
            f"<td style='{cell_style}'>{html.escape(str(row[column]))}</td>"
            for column in columns
        )

        rows.append(
            f"<tr style='background-color: {background}; color: #111827;'>"
            f"{cells}</tr>"
        )

    st.markdown(
        """
        <style>
        .ra-table-wrap {
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 6px;
            max-height: 680px;
            overflow: auto;
        }
        .ra-table {
            border-collapse: collapse;
            width: 100%;
            min-width: 760px;
            font-size: 14px;
        }
        .ra-table th {
            background-color: #111827;
            color: #f9fafb;
            font-weight: 700;
            padding: 10px 12px;
            position: sticky;
            top: 0;
            text-align: left;
            z-index: 1;
        }
        .ra-table td {
            border-top: 1px solid rgba(17, 24, 39, 0.12);
            color: #111827;
            font-weight: 650;
            padding: 9px 12px;
            white-space: nowrap;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div class='ra-table-wrap'>"
        "<table class='ra-table'>"
        f"<thead><tr>{header}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
        "</div>",
        unsafe_allow_html=True,
    )


def build_market_summary(df):

    rows = []

    for market in ("SET", "USA"):

        data = df[df["Market"] == market]

        rows.append({
            "Market": market,
            "Stocks": len(data),
            "BUY": int((data["_signal_group"] == "BUY").sum()),
            "WATCH": int((data["_signal_group"] == "WATCH").sum()),
            "EARLY": int((data["_signal_group"] == "EARLY").sum()),
            "EXTENDED": int((data["_signal_group"] == "EXTENDED").sum()),
            "SKIP": int((data["_signal_group"] == "SKIP").sum()),
            "Avg Score": round(data["StrategyScore"].mean(), 1)
            if not data.empty
            else 0,
            "Max Score": data["StrategyScore"].max()
            if not data.empty
            else 0,
        })

    return pd.DataFrame(rows)


def render_summary(df):

    summary = build_market_summary(df)

    st.subheader("Market Summary")

    metric_cols = st.columns(2)

    for index, market in enumerate(("SET", "USA")):

        data = summary[summary["Market"] == market].iloc[0]

        with metric_cols[index]:
            c1, c2, c3 = st.columns(3)
            c1.metric(f"{market} Stocks", int(data["Stocks"]))
            c2.metric(f"{market} BUY", int(data["BUY"]))
            c3.metric(f"{market} Max", int(data["Max Score"]))

    st.dataframe(
        summary,
        use_container_width=True,
        hide_index=True,
    )


def render_top_market(df, market):

    st.subheader(f"Top {market}")

    top = sort_results(
        df[
            (df["Market"] == market)
            &
            (df["_signal_group"] != "SKIP")
        ]
    ).head(10)

    if top.empty:
        st.info(f"No {market} results")
        return

    render_table(top)


def render_add_to_watchlist(df):

    candidates = df[
        df["_signal_group"] != "SKIP"
    ].copy()

    if candidates.empty:
        return

    st.subheader("Watchlist")

    labels = [
        watchlist_label(row)
        for _, row in candidates.iterrows()
    ]

    with st.form("scanner_add_watchlist_form"):
        selected = st.selectbox(
            "Candidate",
            labels,
        )
        row = selected_candidate_row(
            candidates,
            selected,
        )
        stop_loss_default = first_existing_number(
            row,
            [
                "StopLoss",
                "Stop Loss",
                "Stop_Loss",
                "SL",
            ],
        )
        target_default = first_existing_number(
            row,
            [
                "Target",
                "TakeProfit",
                "Take Profit",
                "TP",
            ],
        )
        note = st.text_input(
            "Note",
            value="",
        )
        stop_loss = st.number_input(
            "Stop Loss",
            min_value=0.0,
            value=stop_loss_default,
            step=0.01,
        )
        target = st.number_input(
            "Target",
            min_value=0.0,
            value=target_default,
            step=0.01,
        )
        submitted = st.form_submit_button(
            "Add to Watchlist"
        )

    if not submitted:
        return

    add_to_watchlist(
        row["Symbol"],
        row["Market"],
        price=safe_number(row.get("Price", 0.0)),
        setup=row.get("Setup", ""),
        score=safe_number(row.get("Score", 0.0)),
        signal=row.get("Signal", ""),
        strategy_mode=row.get("StrategyMode", "Standard"),
        strategy_setup=row.get("StrategySetup", row.get("Setup", "")),
        strategy_score=safe_number(
            row.get(
                "StrategyScore",
                row.get("Score", 0.0),
            )
        ),
        strategy_signal=row.get("StrategySignal", row.get("Signal", "")),
        lifecycle_state=row.get("LifecycleState", "UNKNOWN"),
        previous_lifecycle_state=row.get(
            "PreviousLifecycleState",
            "UNKNOWN",
        ),
        days_in_state=safe_number(row.get("DaysInState", 0)),
        state_changed=row.get("StateChanged", False),
        stop_loss=stop_loss,
        target=target,
        note=note,
    )

    st.success(f"Added {row['Symbol']} to Watchlist")


def run_scanner_from_dashboard(force_refresh, mode, workers, strategy_mode):

    command = [
        sys.executable,
        "scanner.py",
        "--mode",
        mode,
        "--workers",
        str(workers),
        "--strategy-mode",
        strategy_mode.lower(),
    ]

    if force_refresh:
        command.append("--force-refresh")

    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )


def render_scanner_actions():

    st.sidebar.header("Scanner")
    st.sidebar.caption(f"Price cache: {PRICE_CACHE_DIR}")
    scan_mode = st.sidebar.selectbox(
        "Scan Mode",
        SCAN_MODE_OPTIONS,
        key="scanner_scan_mode",
    )
    workers = st.sidebar.number_input(
        "Workers",
        min_value=1,
        max_value=32,
        value=int(MAX_WORKERS),
        step=1,
        key="scanner_workers",
    )
    strategy_mode = st.sidebar.selectbox(
        "Strategy Mode",
        STRATEGY_MODE_OPTIONS,
        key="scanner_strategy_mode",
    )
    run_clicked = st.sidebar.button(
        "Run Scanner"
    )
    force_clicked = st.sidebar.button(
        "Force Refresh"
    )

    if not run_clicked and not force_clicked:
        return

    with st.spinner(
        "Running scanner..."
    ):
        result = run_scanner_from_dashboard(
            force_refresh=force_clicked,
            mode=scan_mode,
            workers=workers,
            strategy_mode=strategy_mode,
        )

    output = (
        (result.stdout or "")
        + "\n"
        + (result.stderr or "")
    ).strip()

    if result.returncode == 0:
        st.success("Scanner completed.")
    else:
        st.error(
            f"Scanner failed with exit code {result.returncode}."
        )

    if output:
        with st.expander("Scanner Output"):
            st.code(
                output[-12000:],
                language="text",
            )


def scanner_page():

    st.title("River Alpha Scanner")
    render_scanner_actions()

    if not RESULT_FILE.exists():
        st.error("scanner_results.xlsx not found")
        st.info("Run: python scanner.py or use Force Refresh")
        return

    df = pd.read_excel(RESULT_FILE)
    df = prepare_data(df)

    last_scan = datetime.fromtimestamp(
        RESULT_FILE.stat().st_mtime
    ).strftime("%d/%m/%Y %H:%M:%S")

    st.caption(f"Last Scan: {last_scan}")
    st.caption(f"Strategy Mode: {current_strategy_mode(df)}")

    render_market_quality_cards(
        df,
        last_scan,
    )

    render_lifecycle_section(df)

    st.sidebar.header("Filter")

    market_filter = st.sidebar.selectbox(
        "Market",
        [
            "ALL",
            "SET",
            "USA",
        ],
    )

    symbol_search = st.sidebar.text_input(
        "Symbol Search",
        value="",
        placeholder="AAPL, PTT, DUK",
    )

    signal_filter = st.sidebar.multiselect(
        "Strategy Signal",
        [
            "ALL",
            "BUY",
            "WATCH",
            "EARLY",
            "EXTENDED",
            "SKIP",
        ],
        default=[
            "BUY",
            "WATCH",
            "EARLY",
            "EXTENDED",
        ],
    )

    lifecycle_filter = st.sidebar.multiselect(
        "Lifecycle State",
        LIFECYCLE_STATES,
        default=[
            "ALL",
        ],
    )

    state_changed_only = st.sidebar.checkbox(
        "State Changed Only",
        value=False,
    )

    render_summary(df)

    st.divider()

    top_cols = st.columns(2)

    with top_cols[0]:
        render_top_market(df, "SET")

    with top_cols[1]:
        render_top_market(df, "USA")

    st.divider()

    filtered = apply_filters(
        df,
        market_filter,
        signal_filter,
        symbol_search,
        lifecycle_filter,
        state_changed_only,
    )

    st.subheader("Scanner Results")

    if filtered.empty:
        st.info("No results")
        return

    render_add_to_watchlist(filtered)

    render_table(filtered)
