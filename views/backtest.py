from datetime import date, timedelta

import pandas as pd
import streamlit as st

from backtest_engine import (
    EQUITY_FILE,
    INITIAL_CAPITAL,
    MONTHLY_FILE,
    SUMMARY_FILE,
    TRADES_FILE,
    run_strategy_lab,
)
from strategy_history import (
    BENCHMARK_FILE,
    DEFAULT_VERSION,
    HISTORY_FILE,
    compare_benchmark,
    compare_runs,
    load_benchmark,
    load_strategy_history,
    save_strategy_run,
)


try:
    import plotly.express as px

    PLOTLY_AVAILABLE = True
except Exception:
    px = None
    PLOTLY_AVAILABLE = False


SUMMARY_METRICS = [
    "Initial Capital",
    "Final Equity",
    "Total Return %",
    "Max Drawdown %",
    "Total Trades",
    "Win Rate",
    "Profit Factor",
    "Avg Win",
    "Avg Loss",
    "Best Trade",
    "Worst Trade",
    "Avg Holding Days",
]
PERCENT_METRICS = {
    "Total Return %",
    "Max Drawdown %",
    "Win Rate",
    "Avg Win",
    "Avg Loss",
    "Best Trade",
    "Worst Trade",
}
MONTHLY_COLUMNS = [
    "Year",
    "Month",
    "MonthlyReturnPct",
]
TRADE_ANALYSIS_COLUMNS = [
    "Symbol",
    "EntryDate",
    "ExitDate",
    "EntryPrice",
    "ExitPrice",
    "HoldingDays",
    "EntryScore",
    "ExitScore",
    "ExitReason",
    "NetReturnPct",
    "WinLoss",
]
BENCHMARK_OPTIONS = [
    "None",
    "Buy & Hold",
    "SET Index",
    "SET50",
    "SET100",
    "NASDAQ100",
    "S&P500",
]
HISTORY_DISPLAY_COLUMNS = [
    "RunID",
    "Date",
    "Symbol",
    "Version",
    "Return",
    "Profit Factor",
    "Win Rate",
    "Drawdown",
    "Trades",
]
COMPARISON_PERCENT_METRICS = {
    "Total Return",
    "Annual Return",
    "Max Drawdown",
    "Win Rate",
    "Average Return",
}


def available_columns(df, columns):

    return [
        column
        for column in columns
        if column in df.columns
    ]


def format_metric_value(metric, value):

    value = float(
        value
        if pd.notna(value)
        else 0
    )
    suffix = "%" if metric in COMPARISON_PERCENT_METRICS else ""

    return f"{value:,.2f}{suffix}"


def render_benchmark_cards(comparison):

    if comparison.empty:
        st.info("No benchmark comparison")
        return

    for _, row in comparison.iterrows():
        metric = row["Metric"]
        c1, c2, c3 = st.columns(3)

        c1.metric(
            f"River Alpha {metric}",
            format_metric_value(
                metric,
                row["River Alpha"],
            ),
        )
        c2.metric(
            f"Benchmark {metric}",
            format_metric_value(
                metric,
                row["Benchmark"],
            ),
        )
        c3.metric(
            f"Difference {metric}",
            format_metric_value(
                metric,
                row["Difference"],
            ),
        )


def render_equity_comparison(
    equity_curve,
    benchmark_curve,
    start_date,
    initial_capital=INITIAL_CAPITAL,
):

    if benchmark_curve.empty:
        st.info("No benchmark equity curve")
        return

    rows = [
        {
            "Date": pd.to_datetime(start_date),
            "Equity": float(initial_capital),
            "Series": "River Alpha",
        }
    ]

    if not equity_curve.empty:
        strategy = equity_curve.copy()
        strategy["Date"] = pd.to_datetime(
            strategy["ExitDate"],
            errors="coerce",
        )
        strategy["Equity"] = pd.to_numeric(
            strategy["Equity"],
            errors="coerce",
        )
        strategy = strategy.dropna(
            subset=[
                "Date",
                "Equity",
            ]
        )

        rows.extend(
            [
                {
                    "Date": row["Date"],
                    "Equity": row["Equity"],
                    "Series": "River Alpha",
                }
                for _, row in strategy.iterrows()
            ]
        )

    benchmark = benchmark_curve.copy()
    benchmark["Date"] = pd.to_datetime(
        benchmark["Date"],
        errors="coerce",
    )
    benchmark["Equity"] = pd.to_numeric(
        benchmark["BenchmarkEquity"],
        errors="coerce",
    )
    benchmark_name = benchmark["Benchmark"].iloc[0]
    benchmark = benchmark.dropna(
        subset=[
            "Date",
            "Equity",
        ]
    )

    rows.extend(
        [
            {
                "Date": row["Date"],
                "Equity": row["Equity"],
                "Series": benchmark_name,
            }
            for _, row in benchmark.iterrows()
        ]
    )

    chart = pd.DataFrame(rows)

    st.subheader("Equity Comparison")

    if PLOTLY_AVAILABLE:
        fig = px.line(
            chart,
            x="Date",
            y="Equity",
            color="Series",
            title="River Alpha Equity vs Benchmark Equity",
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
        )
        return

    pivot = chart.pivot_table(
        index="Date",
        columns="Series",
        values="Equity",
        aggfunc="last",
    ).sort_index()
    st.line_chart(
        pivot,
        use_container_width=True,
    )


def render_benchmark_section(
    benchmark_name,
    benchmark_curve,
    benchmark_comparison,
    equity_curve,
    start_date,
):

    if not benchmark_name or benchmark_name == "None":
        return

    st.header("Benchmark")
    st.caption(f"Benchmark output: {BENCHMARK_FILE}")

    if benchmark_curve.empty:
        st.warning("No benchmark data found for the selected period.")
        return

    render_benchmark_cards(benchmark_comparison)
    render_equity_comparison(
        equity_curve,
        benchmark_curve,
        start_date,
    )


def strategy_history_display(history):

    display = history.copy()
    display["RunID"] = pd.to_numeric(
        display["RunID"],
        errors="coerce",
    ).fillna(0).astype(int)
    display["Date"] = pd.to_datetime(
        display["RunTimestamp"],
        errors="coerce",
    ).dt.strftime("%Y-%m-%d %H:%M")
    display["Return"] = pd.to_numeric(
        display["TotalReturnPct"],
        errors="coerce",
    ).fillna(0)
    display["Profit Factor"] = pd.to_numeric(
        display["ProfitFactor"],
        errors="coerce",
    ).fillna(0)
    display["Win Rate"] = pd.to_numeric(
        display["WinRate"],
        errors="coerce",
    ).fillna(0)
    display["Drawdown"] = pd.to_numeric(
        display["MaxDrawdown"],
        errors="coerce",
    ).fillna(0)
    display["Trades"] = pd.to_numeric(
        display["TotalTrades"],
        errors="coerce",
    ).fillna(0).astype(int)

    return display[
        available_columns(
            display,
            HISTORY_DISPLAY_COLUMNS,
        )
    ]


def render_history_filters(history):

    c1, c2, c3 = st.columns(3)

    with c1:
        markets = [
            "ALL",
        ] + sorted(
            history["Market"].dropna().astype(str).unique()
        )
        market_filter = st.selectbox(
            "Market",
            markets,
            key="strategy_history_market",
        )

    with c2:
        symbols = [
            "ALL",
        ] + sorted(
            history["Symbol"].dropna().astype(str).unique()
        )
        symbol_filter = st.selectbox(
            "Symbol",
            symbols,
            key="strategy_history_symbol",
        )

    with c3:
        versions = [
            "ALL",
        ] + sorted(
            history["Version"].dropna().astype(str).unique()
        )
        version_filter = st.selectbox(
            "Version",
            versions,
            key="strategy_history_version",
        )

    filtered = history.copy()

    if market_filter != "ALL":
        filtered = filtered[
            filtered["Market"].astype(str) == market_filter
        ]

    if symbol_filter != "ALL":
        filtered = filtered[
            filtered["Symbol"].astype(str) == symbol_filter
        ]

    if version_filter != "ALL":
        filtered = filtered[
            filtered["Version"].astype(str) == version_filter
        ]

    return filtered


def run_label(row):

    run_id = int(
        float(
            row.get(
                "RunID",
                0,
            )
            or 0
        )
    )
    symbol = row.get(
        "Symbol",
        "",
    )
    total_return = pd.to_numeric(
        row.get(
            "TotalReturnPct",
            0,
        ),
        errors="coerce",
    )
    timestamp = row.get(
        "RunTimestamp",
        "",
    )

    return f"#{run_id} {symbol} {total_return:.2f}% {timestamp}"


def render_run_comparison(history):

    st.subheader("Compare Runs")

    if len(history) < 2:
        st.info("Need at least two Strategy Lab runs to compare.")
        return

    ordered = history.copy()
    ordered["RunID"] = pd.to_numeric(
        ordered["RunID"],
        errors="coerce",
    )
    ordered = ordered.dropna(
        subset=[
            "RunID",
        ]
    ).sort_values(
        "RunID",
        ascending=False,
    )

    if len(ordered) < 2:
        st.info("Need at least two Strategy Lab runs to compare.")
        return

    run_ids = ordered["RunID"].astype(int).tolist()
    labels = {
        int(row["RunID"]): run_label(row)
        for _, row in ordered.iterrows()
    }
    c1, c2 = st.columns(2)

    with c1:
        run_a = st.selectbox(
            "Run A",
            run_ids,
            format_func=lambda run_id: labels.get(
                int(run_id),
                str(run_id),
            ),
            key="strategy_compare_run_a",
        )

    with c2:
        run_b = st.selectbox(
            "Run B",
            run_ids,
            index=1,
            format_func=lambda run_id: labels.get(
                int(run_id),
                str(run_id),
            ),
            key="strategy_compare_run_b",
        )

    if int(run_a) == int(run_b):
        st.info("Select two different runs.")
        return

    comparison = compare_runs(
        run_a,
        run_b,
    )

    if comparison.empty:
        st.info("No comparison data")
        return

    run_a_column = f"Run {int(run_a)}"
    run_b_column = f"Run {int(run_b)}"
    display = comparison[
        [
            "Metric",
            "RunA",
            "RunB",
        ]
    ].rename(
        columns={
            "RunA": run_a_column,
            "RunB": run_b_column,
        }
    )

    def highlight_better(_):

        styles = pd.DataFrame(
            "",
            index=display.index,
            columns=display.columns,
        )

        for index, row in comparison.iterrows():
            if row["Better"] == "A":
                styles.loc[index, run_a_column] = (
                    "background-color: #b7f7c6; color: #0f172a;"
                )
            elif row["Better"] == "B":
                styles.loc[index, run_b_column] = (
                    "background-color: #b7f7c6; color: #0f172a;"
                )

        return styles

    styled = display.style.apply(
        highlight_better,
        axis=None,
    ).format(
        {
            run_a_column: "{:,.2f}",
            run_b_column: "{:,.2f}",
        }
    )
    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
    )


def render_strategy_history_dashboard():

    st.header("Strategy History")
    st.caption(f"History file: {HISTORY_FILE}")

    history = load_strategy_history()

    if history.empty:
        st.info("No Strategy Lab history yet.")
        return

    filtered = render_history_filters(history)
    filtered = filtered.copy()
    filtered["RunID"] = pd.to_numeric(
        filtered["RunID"],
        errors="coerce",
    )
    filtered = filtered.dropna(
        subset=[
            "RunID",
        ]
    ).sort_values(
        "RunID",
        ascending=False,
    )

    latest = filtered.head(50)

    st.subheader("Latest 50 Runs")
    st.dataframe(
        strategy_history_display(latest),
        use_container_width=True,
        hide_index=True,
    )
    render_run_comparison(filtered)


def render_summary_cards(summary):

    if summary.empty:
        st.info("No summary")
        return

    row = summary.iloc[0]
    columns = st.columns(4)

    for index, metric in enumerate(SUMMARY_METRICS):
        value = row.get(
            metric,
            0,
        )
        suffix = "%" if metric in PERCENT_METRICS else ""
        columns[index % 4].metric(
            metric,
            f"{float(value):,.2f}{suffix}",
        )


def render_line_chart(df, x, y, title):

    st.subheader(title)

    if df.empty:
        st.info(f"No {title.lower()}")
        return

    chart = df.copy()
    chart[x] = pd.to_datetime(
        chart[x],
        errors="coerce",
    )
    chart = chart.dropna(
        subset=[
            x,
        ]
    )

    if chart.empty:
        st.info(f"No {title.lower()}")
        return

    if PLOTLY_AVAILABLE:
        fig = px.line(
            chart,
            x=x,
            y=y,
            markers=True,
            title=title,
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
        )
        return

    st.line_chart(
        chart.set_index(x)[y],
        use_container_width=True,
    )


def render_monthly_chart(monthly):

    st.subheader("Monthly Returns")

    if monthly.empty:
        st.info("No monthly returns")
        return

    chart = monthly.copy()
    chart["Period"] = (
        chart["Year"].astype(str)
        + "-"
        + chart["Month"].astype(int).astype(str).str.zfill(2)
    )

    if PLOTLY_AVAILABLE:
        fig = px.bar(
            chart,
            x="Period",
            y="MonthlyReturnPct",
            title="Monthly Returns",
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
        )
        return

    st.bar_chart(
        chart.set_index("Period")["MonthlyReturnPct"],
        use_container_width=True,
    )


def render_win_loss_distribution(trades):

    st.subheader("Win/Loss Distribution")

    if trades.empty:
        st.info("No win/loss data")
        return

    distribution = (
        trades["WinLoss"]
        .value_counts()
        .rename_axis("WinLoss")
        .reset_index(name="Trades")
    )

    if PLOTLY_AVAILABLE:
        fig = px.bar(
            distribution,
            x="WinLoss",
            y="Trades",
            title="Win/Loss Distribution",
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
        )
        return

    st.bar_chart(
        distribution.set_index("WinLoss")["Trades"],
        use_container_width=True,
    )


def render_return_distribution(trades):

    st.subheader("Return Distribution")

    if trades.empty:
        st.info("No return data")
        return

    data = trades.copy()
    data["NetReturnPct"] = pd.to_numeric(
        data["NetReturnPct"],
        errors="coerce",
    ).fillna(0)

    if PLOTLY_AVAILABLE:
        fig = px.histogram(
            data,
            x="NetReturnPct",
            nbins=20,
            title="Return Distribution",
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
        )
        return

    buckets = pd.cut(
        data["NetReturnPct"],
        bins=10,
    )
    distribution = buckets.value_counts().sort_index()
    distribution.index = distribution.index.astype(str)
    st.bar_chart(
        distribution,
        use_container_width=True,
    )


def filter_trade_analysis(trades):

    filtered = trades.copy()
    c1, c2, c3 = st.columns(3)

    with c1:
        show_wins = st.checkbox(
            "Show only wins",
            value=False,
        )

    with c2:
        show_losses = st.checkbox(
            "Show only losses",
            value=False,
        )

    with c3:
        reasons = sorted(
            filtered["ExitReason"].dropna().unique()
        )
        selected_reasons = st.multiselect(
            "Filter by ExitReason",
            reasons,
            default=reasons,
        )

    if show_wins and not show_losses:
        filtered = filtered[
            filtered["WinLoss"] == "WIN"
        ]
    elif show_losses and not show_wins:
        filtered = filtered[
            filtered["WinLoss"] == "LOSS"
        ]

    if selected_reasons:
        filtered = filtered[
            filtered["ExitReason"].isin(selected_reasons)
        ]
    else:
        filtered = filtered.iloc[0:0]

    return filtered


def render_performance_dashboard(trades, summary, equity_curve, monthly):

    st.header("Performance Dashboard")

    if trades.empty:
        st.info(
            "No trades found. Try lowering Min Score or expanding date range."
        )
        return

    render_summary_cards(summary)

    chart_left, chart_right = st.columns(2)

    with chart_left:
        render_line_chart(
            equity_curve,
            "ExitDate",
            "Equity",
            "Equity Curve",
        )
        render_monthly_chart(monthly)
        render_win_loss_distribution(trades)

    with chart_right:
        render_line_chart(
            equity_curve,
            "ExitDate",
            "DrawdownPct",
            "Drawdown Curve",
        )
        render_return_distribution(trades)

    st.subheader("Monthly Performance")

    st.dataframe(
        monthly[
            available_columns(
                monthly,
                MONTHLY_COLUMNS,
            )
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Trade Analysis")
    filtered_trades = filter_trade_analysis(trades)

    if filtered_trades.empty:
        st.info("No trades match the selected filters")
    else:
        st.dataframe(
            filtered_trades[
                available_columns(
                    filtered_trades,
                    TRADE_ANALYSIS_COLUMNS,
                )
            ],
            use_container_width=True,
            hide_index=True,
        )


def backtest_page():

    st.title("Strategy Lab")
    st.caption(
        "Phase 2.2: Strategy History and Benchmark comparison build on "
        "Strategy Lab outputs without changing the trading logic."
    )
    st.caption(
        f"Trades: {TRADES_FILE} | Summary: {SUMMARY_FILE} | "
        f"Equity: {EQUITY_FILE} | Monthly: {MONTHLY_FILE} | "
        f"History: {HISTORY_FILE} | Benchmark: {BENCHMARK_FILE}"
    )

    today = date.today()
    default_start = today - timedelta(days=365)

    with st.form("strategy_lab_form"):
        c1, c2, c3 = st.columns(3)

        with c1:
            market = st.selectbox(
                "Market",
                [
                    "SET",
                    "USA",
                ],
            )
            symbol = st.text_input(
                "Symbol",
                value="YONG"
                if market == "SET"
                else "AEP",
            )

        with c2:
            start_date = st.date_input(
                "Start Date",
                value=default_start,
            )
            end_date = st.date_input(
                "End Date",
                value=today,
            )

        with c3:
            min_score = st.number_input(
                "Min Score",
                min_value=0.0,
                max_value=100.0,
                value=70.0,
                step=1.0,
            )

        st.subheader("Exit Rules")
        st.caption(
            "Signal Changed is always active. Optional rules below run before "
            "Signal Changed and the matched rule is recorded as ExitReason."
        )

        r1, r2, r3, r4 = st.columns(4)

        with r1:
            enable_stop_loss = st.checkbox(
                "Stop Loss",
                value=False,
            )
            stop_loss_pct = st.number_input(
                "Stop Loss %",
                min_value=0.1,
                value=8.0,
                step=0.5,
            )

        with r2:
            enable_target = st.checkbox(
                "Target",
                value=False,
            )
            target_pct = st.number_input(
                "Target %",
                min_value=0.1,
                value=20.0,
                step=0.5,
            )

        with r3:
            enable_max_holding_days = st.checkbox(
                "Max Holding Days",
                value=False,
            )
            max_holding_days = st.number_input(
                "Max Days",
                min_value=1,
                value=20,
                step=1,
            )

        with r4:
            enable_trailing_stop = st.checkbox(
                "Trailing Stop",
                value=False,
            )
            trailing_stop_pct = st.number_input(
                "Trailing Stop %",
                min_value=0.1,
                value=10.0,
                step=0.5,
            )

        benchmark_name = st.selectbox(
            "Benchmark",
            BENCHMARK_OPTIONS,
            key="strategy_lab_benchmark",
        )
        st.caption(f"Version: {DEFAULT_VERSION}")

        submitted = st.form_submit_button(
            "Run Strategy Lab"
        )

    if submitted:
        if not symbol.strip():
            st.error("Symbol is required")
        elif start_date >= end_date:
            st.error("Start Date must be before End Date")
        else:
            with st.spinner("Running Strategy Lab..."):
                trades, summary, equity_curve, monthly = run_strategy_lab(
                    symbol=symbol,
                    market=market,
                    start_date=start_date,
                    end_date=end_date,
                    min_score=min_score,
                    enable_stop_loss=enable_stop_loss,
                    stop_loss_pct=stop_loss_pct,
                    enable_target=enable_target,
                    target_pct=target_pct,
                    enable_max_holding_days=enable_max_holding_days,
                    max_holding_days=max_holding_days,
                    enable_trailing_stop=enable_trailing_stop,
                    trailing_stop_pct=trailing_stop_pct,
                )
                run_row = save_strategy_run(
                    market=market,
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    min_score=min_score,
                    summary=summary,
                    trades=trades,
                    stop_loss_enabled=enable_stop_loss,
                    stop_loss_pct=stop_loss_pct,
                    target_enabled=enable_target,
                    target_pct=target_pct,
                    trailing_enabled=enable_trailing_stop,
                    trailing_pct=trailing_stop_pct,
                    max_holding_enabled=enable_max_holding_days,
                    max_holding_days=max_holding_days,
                    initial_capital=INITIAL_CAPITAL,
                    version=DEFAULT_VERSION,
                )
                benchmark_curve = load_benchmark(
                    benchmark=benchmark_name,
                    symbol=symbol,
                    market=market,
                    start_date=start_date,
                    end_date=end_date,
                    initial_capital=INITIAL_CAPITAL,
                )
                benchmark_comparison = compare_benchmark(
                    summary=summary,
                    benchmark_curve=benchmark_curve,
                    start_date=start_date,
                    end_date=end_date,
                    initial_capital=INITIAL_CAPITAL,
                )

            st.success(
                f"Strategy Lab completed. Saved RunID {run_row['RunID']}."
            )
            render_performance_dashboard(
                trades,
                summary,
                equity_curve,
                monthly,
            )
            render_benchmark_section(
                benchmark_name,
                benchmark_curve,
                benchmark_comparison,
                equity_curve,
                start_date,
            )

    st.divider()
    render_strategy_history_dashboard()
