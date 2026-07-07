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
from strategy_optimizer import (
    OPTIMIZER_COLUMNS,
    OPTIMIZER_FILE,
    build_parameter_range,
    count_optimizer_combinations,
    run_strategy_optimizer,
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
from strategy_presets import (
    DEFAULT_PARAMETERS,
    DEFAULT_PRESET_FILE,
    build_preset_performance_table,
    compare_parameters,
    delete_preset,
    export_preset_json,
    import_preset_json,
    load_presets,
    normalize_parameters,
    parameters_from_optimizer_row,
    reset_default_presets,
    save_preset,
    validate_parameters,
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
    "Median Return",
    "Return Std",
    "Average RR",
    "Average MAE",
    "Average MFE",
]
PERCENT_METRICS = {
    "Total Return %",
    "Max Drawdown %",
    "Win Rate",
    "Avg Win",
    "Avg Loss",
    "Best Trade",
    "Worst Trade",
    "Median Return",
    "Return Std",
    "Average MAE",
    "Average MFE",
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
    "Commission",
    "NetReturnPct",
    "MAE",
    "MFE",
    "RiskPct",
    "RR",
    "WinLoss",
]
TRADE_ANALYTIC_DEFAULTS = [
    "Commission",
    "NetReturnPct",
    "MAE",
    "MFE",
    "RiskPct",
    "RR",
]
MONTH_LABELS = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}
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
OPTIMIZER_RANGE_HELP = "Use 0 to disable optional exit rules for that parameter."
STRATEGY_LAB_PARAM_KEYS = {
    "min_score": "strategy_lab_min_score",
    "enable_stop_loss": "strategy_lab_enable_stop_loss",
    "stop_loss_pct": "strategy_lab_stop_loss_pct",
    "enable_target": "strategy_lab_enable_target",
    "target_pct": "strategy_lab_target_pct",
    "enable_trailing_stop": "strategy_lab_enable_trailing_stop",
    "trailing_stop_pct": "strategy_lab_trailing_stop_pct",
    "enable_max_holding_days": "strategy_lab_enable_max_holding_days",
    "max_holding_days": "strategy_lab_max_holding_days",
}


def ensure_strategy_lab_defaults():

    for parameter, key in STRATEGY_LAB_PARAM_KEYS.items():
        st.session_state.setdefault(
            key,
            DEFAULT_PARAMETERS[parameter],
        )

    st.session_state.setdefault(
        "strategy_lab_market",
        "SET",
    )
    st.session_state.setdefault(
        "strategy_lab_symbol",
        "YONG",
    )


def strategy_lab_parameters_from_state():

    return normalize_parameters({
        parameter: st.session_state.get(
            key,
            DEFAULT_PARAMETERS[parameter],
        )
        for parameter, key in STRATEGY_LAB_PARAM_KEYS.items()
    })


def strategy_lab_parameters_from_values(
    min_score,
    enable_stop_loss,
    stop_loss_pct,
    enable_target,
    target_pct,
    enable_max_holding_days,
    max_holding_days,
    enable_trailing_stop,
    trailing_stop_pct,
):

    return normalize_parameters({
        "min_score": min_score,
        "enable_stop_loss": enable_stop_loss,
        "stop_loss_pct": stop_loss_pct,
        "enable_target": enable_target,
        "target_pct": target_pct,
        "enable_max_holding_days": enable_max_holding_days,
        "max_holding_days": max_holding_days,
        "enable_trailing_stop": enable_trailing_stop,
        "trailing_stop_pct": trailing_stop_pct,
    })


def apply_preset_to_state(preset):

    parameters = normalize_parameters(
        preset.get(
            "Parameters",
            {},
        )
    )

    for parameter, key in STRATEGY_LAB_PARAM_KEYS.items():
        st.session_state[key] = parameters[parameter]


def load_optimizer_results():

    if not OPTIMIZER_FILE.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(OPTIMIZER_FILE)
    except Exception:
        return pd.DataFrame()


def render_preset_badges(presets):

    if not presets:
        return

    history = load_strategy_history()
    optimizer_results = load_optimizer_results()
    performance = build_preset_performance_table(
        presets,
        history,
        optimizer_results,
    )

    st.subheader("Performance Badges")
    st.caption(
        "Badges are calculated from matching Strategy History first, then "
        "Optimizer Results if no matching history exists."
    )

    for start in range(0, len(performance), 3):
        columns = st.columns(3)

        for column, (_, row) in zip(
            columns,
            performance.iloc[start:start + 3].iterrows(),
        ):
            with column:
                with st.container(border=True):
                    st.markdown(f"**{row['Preset']}**")
                    st.markdown(str(row["Stars"]))

                    if row["Trades"]:
                        st.caption(
                            f"Win Rate {safe_float(row['WinRate']):,.2f}%"
                        )
                        st.caption(
                            f"PF {safe_float(row['ProfitFactor']):,.2f}"
                        )
                        st.caption(
                            f"{row['Source']} | "
                            f"{int(row['Runs'])} runs | "
                            f"{int(row['Trades'])} trades"
                        )
                    else:
                        st.caption("No matching backtest data yet")


def render_preset_actions(presets, selected_preset):

    current_parameters = strategy_lab_parameters_from_state()
    save_name = st.text_input(
        "Preset Name",
        value="My Breakout",
        key="strategy_preset_save_name",
    )
    save_description = st.text_area(
        "Description",
        value="Custom Strategy Lab preset",
        key="strategy_preset_save_description",
        height=80,
    )
    save_author = st.text_input(
        "Author",
        value="Natja",
        key="strategy_preset_author",
    )
    b1, b2, b3, b4, b5 = st.columns(5)

    with b1:
        if st.button("Load", key="strategy_preset_load"):
            apply_preset_to_state(selected_preset)
            st.success(f"Loaded {selected_preset['Name']}")
            st.rerun()

    with b2:
        if st.button("Save As New", key="strategy_preset_save_new"):
            errors = validate_parameters(current_parameters)

            if not save_name.strip():
                st.error("Preset Name is required.")
            elif errors:
                st.error(" ".join(errors))
            else:
                path = save_preset(
                    name=save_name,
                    description=save_description,
                    author=save_author,
                    parameters=current_parameters,
                )
                st.success(f"Saved preset: {path}")
                st.rerun()

    with b3:
        if st.button("Update Current", key="strategy_preset_update"):
            errors = validate_parameters(current_parameters)

            if errors:
                st.error(" ".join(errors))
            else:
                path = save_preset(
                    name=selected_preset["Name"],
                    description=selected_preset.get(
                        "Description",
                        "",
                    ),
                    author=selected_preset.get(
                        "Author",
                        save_author,
                    ),
                    parameters=current_parameters,
                    version=selected_preset.get("Version"),
                )
                st.success(f"Updated preset: {path}")
                st.rerun()

    with b4:
        if st.button("Delete", key="strategy_preset_delete"):
            deleted, message = delete_preset(
                selected_preset["Name"]
            )

            if deleted:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

    with b5:
        if st.button("Reset", key="strategy_preset_reset"):
            reset_default_presets()
            st.success("Default presets reset.")
            st.rerun()

    export_name = f"{selected_preset['Name']}.json"
    st.download_button(
        "Export preset JSON",
        data=export_preset_json(selected_preset),
        file_name=export_name,
        mime="application/json",
        key="strategy_preset_export",
    )
    uploaded = st.file_uploader(
        "Import preset JSON",
        type=[
            "json",
        ],
        key="strategy_preset_import_file",
    )

    if uploaded and st.button("Import Preset", key="strategy_preset_import"):
        try:
            paths = import_preset_json(
                uploaded.getvalue().decode("utf-8")
            )
            st.success(f"Imported {len(paths)} preset file(s).")
            st.rerun()
        except Exception as error:
            st.error(f"Import failed: {error}")


def render_preset_section():

    ensure_strategy_lab_defaults()
    presets = load_presets()

    st.header("Strategy Presets")
    st.caption(f"Preset folder: {DEFAULT_PRESET_FILE.parent}")

    if not presets:
        st.warning("No presets found.")
        return presets

    names = list(presets.keys())
    selected_name = st.selectbox(
        "Preset",
        names,
        key="strategy_preset_selected",
    )
    selected_preset = presets[selected_name]
    previous_name = st.session_state.get(
        "_strategy_preset_last_selected"
    )

    if previous_name != selected_name:
        apply_preset_to_state(selected_preset)
        st.session_state["_strategy_preset_last_selected"] = selected_name

    render_preset_badges(presets)

    with st.expander("Preset Manager", expanded=True):
        st.write(selected_preset.get("Description", ""))
        render_preset_actions(
            presets,
            selected_preset,
        )

    return presets


def render_preset_comparison(current_parameters, presets):

    if not presets:
        return

    st.subheader("Current vs Preset")
    compare_name = st.selectbox(
        "Compare Preset",
        list(presets.keys()),
        key="strategy_preset_compare_name",
    )
    comparison = compare_parameters(
        current_parameters,
        presets[compare_name].get(
            "Parameters",
            {},
        ),
    )

    def highlight_changes(row):

        if row.get("Changed"):
            return [
                "background-color: #78350f; color: #fef3c7;"
                for _ in row
            ]

        return [
            ""
            for _ in row
        ]

    st.dataframe(
        comparison.style.apply(
            highlight_changes,
            axis=1,
        ),
        use_container_width=True,
        hide_index=True,
    )


def available_columns(df, columns):

    return [
        column
        for column in columns
        if column in df.columns
    ]


def safe_float(value, default=0):

    try:
        if pd.isna(value):
            return float(default)

        return float(value)
    except (TypeError, ValueError):
        return float(default)


def ensure_trade_analysis_defaults(trades):

    df = trades.copy()

    for column in TRADE_ANALYTIC_DEFAULTS:
        if column not in df.columns:
            df[column] = 0

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        ).fillna(0)

    return df


def ensure_equity_curve_defaults(equity_curve):

    df = equity_curve.copy()

    if df.empty:
        return df

    if "Equity" not in df.columns:
        df["Equity"] = INITIAL_CAPITAL

    df["Equity"] = pd.to_numeric(
        df["Equity"],
        errors="coerce",
    ).fillna(INITIAL_CAPITAL)

    if "PeakEquity" not in df.columns:
        df["PeakEquity"] = df["Equity"].cummax()

    df["PeakEquity"] = pd.to_numeric(
        df["PeakEquity"],
        errors="coerce",
    ).fillna(df["Equity"]).cummax()

    if "DrawdownPct" not in df.columns:
        df["DrawdownPct"] = (
            df["Equity"] / df["PeakEquity"] - 1
        ) * 100

    if "IsNewHigh" not in df.columns:
        df["IsNewHigh"] = df["Equity"] >= df["PeakEquity"]

    return df


def format_metric_value(metric, value):

    value = safe_float(value)
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
            f"{safe_float(value):,.2f}{suffix}",
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


def render_monthly_heatmap(monthly):

    st.subheader("Monthly Heatmap")

    if monthly.empty:
        st.info("No monthly heatmap")
        return

    data = monthly.copy()
    data["Year"] = pd.to_numeric(
        data["Year"],
        errors="coerce",
    )
    data["Month"] = pd.to_numeric(
        data["Month"],
        errors="coerce",
    )
    data["MonthlyReturnPct"] = pd.to_numeric(
        data["MonthlyReturnPct"],
        errors="coerce",
    )
    data = data.dropna(
        subset=[
            "Year",
            "Month",
            "MonthlyReturnPct",
        ]
    )

    if data.empty:
        st.info("No monthly heatmap")
        return

    data["Year"] = data["Year"].astype(int)
    data["Month"] = data["Month"].astype(int)
    heatmap = data.pivot_table(
        index="Year",
        columns="Month",
        values="MonthlyReturnPct",
        aggfunc="sum",
    ).reindex(
        columns=list(range(1, 13))
    )
    heatmap = heatmap.rename(
        columns=MONTH_LABELS
    )
    max_abs_return = max(
        abs(
            safe_float(
                heatmap.min().min()
            )
        ),
        abs(
            safe_float(
                heatmap.max().max()
            )
        ),
        1,
    )

    if PLOTLY_AVAILABLE:
        fig = px.imshow(
            heatmap,
            aspect="auto",
            color_continuous_scale=[
                (0, "#ef4444"),
                (0.5, "#f8fafc"),
                (1, "#22c55e"),
            ],
            labels={
                "x": "Month",
                "y": "Year",
                "color": "Return %",
            },
            text_auto=".2f",
            zmin=-max_abs_return,
            zmax=max_abs_return,
            title="Monthly Return Heatmap",
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
        )
        return

    st.dataframe(
        heatmap.fillna(0).round(2),
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


def render_return_distribution_stats(trades):

    returns = pd.to_numeric(
        trades["NetReturnPct"],
        errors="coerce",
    ).fillna(0)

    stats = {
        "Mean Return": returns.mean(),
        "Median Return": returns.median(),
        "Std Return": returns.std(ddof=0),
        "Skew": returns.skew() if len(returns) > 2 else 0,
    }
    columns = st.columns(4)

    for index, (label, value) in enumerate(stats.items()):
        suffix = "" if label == "Skew" else "%"
        columns[index].metric(
            label,
            f"{safe_float(value):,.2f}{suffix}",
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
    render_return_distribution_stats(data)

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

    trades = ensure_trade_analysis_defaults(trades)
    equity_curve = ensure_equity_curve_defaults(equity_curve)

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
        render_monthly_heatmap(monthly)
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


def render_float_range(
    label,
    key_prefix,
    start_default,
    end_default,
    step_default,
    min_value=0.0,
    max_value=100.0,
):

    st.markdown(f"**{label}**")
    c1, c2, c3 = st.columns(3)

    with c1:
        start = st.number_input(
            "From",
            min_value=float(min_value),
            max_value=float(max_value),
            value=float(start_default),
            step=0.5,
            key=f"{key_prefix}_start",
        )

    with c2:
        end = st.number_input(
            "To",
            min_value=float(min_value),
            max_value=float(max_value),
            value=float(end_default),
            step=0.5,
            key=f"{key_prefix}_end",
        )

    with c3:
        step = st.number_input(
            "Step",
            min_value=0.1,
            max_value=float(max_value),
            value=float(step_default),
            step=0.5,
            key=f"{key_prefix}_step",
        )

    return start, end, step


def render_int_range(
    label,
    key_prefix,
    start_default,
    end_default,
    step_default,
    min_value=0,
    max_value=365,
):

    st.markdown(f"**{label}**")
    c1, c2, c3 = st.columns(3)

    with c1:
        start = st.number_input(
            "From",
            min_value=int(min_value),
            max_value=int(max_value),
            value=int(start_default),
            step=1,
            key=f"{key_prefix}_start",
        )

    with c2:
        end = st.number_input(
            "To",
            min_value=int(min_value),
            max_value=int(max_value),
            value=int(end_default),
            step=1,
            key=f"{key_prefix}_end",
        )

    with c3:
        step = st.number_input(
            "Step",
            min_value=1,
            max_value=int(max_value),
            value=int(step_default),
            step=1,
            key=f"{key_prefix}_step",
        )

    return start, end, step


def render_optimizer_results(results):

    st.subheader("Optimizer Results")

    if results.empty:
        st.info("No optimizer results")
        return

    display = results[
        available_columns(
            results,
            OPTIMIZER_COLUMNS,
        )
    ].copy()

    def highlight_best_row(row):

        if row.name == display.index[0]:
            return [
                "background-color: #14532d; color: #f8fafc;"
                for _ in row
            ]

        return [
            ""
            for _ in row
        ]

    numeric_columns = {
        column: "{:,.2f}"
        for column in display.columns
        if column != "TotalTrades"
    }

    styled = display.style.apply(
        highlight_best_row,
        axis=1,
    ).format(
        numeric_columns
    )
    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
    )

    best = results.iloc[0]
    best_parameters = parameters_from_optimizer_row(best)

    with st.expander("Save Best Result as Preset"):
        default_name = (
            "Optimizer "
            f"PF {safe_float(best.get('ProfitFactor')):,.2f} "
            f"Return {safe_float(best.get('TotalReturnPct')):,.2f}%"
        )
        preset_name = st.text_input(
            "Preset Name",
            value=default_name,
            key="optimizer_best_preset_name",
        )
        preset_description = st.text_area(
            "Description",
            value=(
                "Created from the best Strategy Optimizer result. "
                f"Win Rate {safe_float(best.get('WinRate')):,.2f}%, "
                f"PF {safe_float(best.get('ProfitFactor')):,.2f}."
            ),
            key="optimizer_best_preset_description",
            height=80,
        )
        preset_author = st.text_input(
            "Author",
            value="Natja",
            key="optimizer_best_preset_author",
        )

        if st.button(
            "Save Best Result as Preset",
            key="optimizer_save_best_preset",
        ):
            errors = validate_parameters(best_parameters)

            if not preset_name.strip():
                st.error("Preset Name is required.")
            elif errors:
                st.error(" ".join(errors))
            else:
                path = save_preset(
                    name=preset_name,
                    description=preset_description,
                    author=preset_author,
                    parameters=best_parameters,
                )
                st.success(f"Saved preset: {path}")


def render_optimizer_section():

    st.header("Optimizer")
    st.caption(
        "Runs multiple Strategy Lab parameter combinations with the same "
        "engine. Scanner, Watchlist, Portfolio and Decision Engine are not "
        "changed."
    )
    st.caption(f"Optimizer output: {OPTIMIZER_FILE}")

    today = date.today()
    default_start = today - timedelta(days=365)
    range_error = None
    combination_count = 0
    confirm_large = True

    with st.form("strategy_optimizer_form"):
        c1, c2, c3 = st.columns(3)

        with c1:
            market = st.selectbox(
                "Market",
                [
                    "SET",
                    "USA",
                ],
                key="optimizer_market",
            )
            symbol = st.text_input(
                "Symbol",
                value="YONG"
                if market == "SET"
                else "AEP",
                key="optimizer_symbol",
            )

        with c2:
            start_date = st.date_input(
                "Start Date",
                value=default_start,
                key="optimizer_start_date",
            )
            end_date = st.date_input(
                "End Date",
                value=today,
                key="optimizer_end_date",
            )

        with c3:
            st.caption(OPTIMIZER_RANGE_HELP)

        r1, r2 = st.columns(2)

        with r1:
            min_score_range = render_float_range(
                "Min Score",
                "optimizer_min_score",
                70.0,
                90.0,
                5.0,
                0.0,
                100.0,
            )
            stop_loss_range = render_float_range(
                "Stop Loss %",
                "optimizer_stop_loss",
                3.0,
                10.0,
                1.0,
                0.0,
                100.0,
            )
            target_range = render_float_range(
                "Target %",
                "optimizer_target",
                10.0,
                30.0,
                5.0,
                0.0,
                300.0,
            )

        with r2:
            max_holding_range = render_int_range(
                "Max Holding Days",
                "optimizer_max_holding",
                0,
                20,
                10,
                0,
                365,
            )
            trailing_stop_range = render_float_range(
                "Trailing Stop %",
                "optimizer_trailing_stop",
                0.0,
                10.0,
                5.0,
                0.0,
                100.0,
            )

        try:
            min_scores = build_parameter_range(*min_score_range)
            stop_losses = build_parameter_range(*stop_loss_range)
            targets = build_parameter_range(*target_range)
            max_holding_days = build_parameter_range(
                *max_holding_range,
                as_int=True,
            )
            trailing_stops = build_parameter_range(*trailing_stop_range)
            combination_count = count_optimizer_combinations(
                min_scores,
                stop_losses,
                targets,
                max_holding_days,
                trailing_stops,
            )
        except ValueError as error:
            min_scores = []
            stop_losses = []
            targets = []
            max_holding_days = []
            trailing_stops = []
            range_error = str(error)

        st.caption(f"Combinations: {combination_count}")

        if combination_count > 200:
            st.warning(
                "This will run more than 200 combinations and may take a while."
            )
            confirm_large = st.checkbox(
                "Confirm large optimization",
                value=False,
                key="optimizer_confirm_large",
            )

        submitted = st.form_submit_button(
            "Run Optimizer"
        )

    if submitted:
        if range_error:
            st.error(range_error)
        elif not symbol.strip():
            st.error("Symbol is required")
        elif start_date >= end_date:
            st.error("Start Date must be before End Date")
        elif combination_count > 200 and not confirm_large:
            st.error(
                "Please confirm before running more than 200 combinations."
            )
        else:
            progress_bar = st.progress(0)
            status = st.empty()

            def update_progress(current, total, row):

                progress_bar.progress(
                    current / total
                    if total
                    else 0
                )
                status.write(
                    f"Running {current}/{total} | "
                    f"ProfitFactor {safe_float(row.get('ProfitFactor')):,.2f} | "
                    f"Return {safe_float(row.get('TotalReturnPct')):,.2f}%"
                )

            try:
                with st.spinner("Running Optimizer..."):
                    results = run_strategy_optimizer(
                        symbol=symbol,
                        market=market,
                        start_date=start_date,
                        end_date=end_date,
                        min_scores=min_scores,
                        stop_loss_pcts=stop_losses,
                        target_pcts=targets,
                        max_holding_days=max_holding_days,
                        trailing_stop_pcts=trailing_stops,
                        progress_callback=update_progress,
                    )

                progress_bar.progress(1.0)
                status.write("Optimizer completed")
                st.success(
                    f"Optimizer completed. Saved {len(results)} rows."
                )
                render_optimizer_results(results)
            except Exception as error:
                st.error(f"Optimizer failed: {error}")

    if not submitted and OPTIMIZER_FILE.exists():
        try:
            existing = pd.read_csv(OPTIMIZER_FILE)
            render_optimizer_results(existing)
        except Exception as error:
            st.warning(f"Could not load optimizer results: {error}")


def backtest_page():

    st.title("Strategy Lab")
    st.caption(
        "v1.1.2: Strategy Presets save and apply Strategy Lab parameters "
        "without changing the trading logic."
    )
    st.caption(
        f"Trades: {TRADES_FILE} | Summary: {SUMMARY_FILE} | "
        f"Equity: {EQUITY_FILE} | Monthly: {MONTHLY_FILE} | "
        f"History: {HISTORY_FILE} | Benchmark: {BENCHMARK_FILE}"
    )

    today = date.today()
    default_start = today - timedelta(days=365)
    presets = render_preset_section()

    with st.form("strategy_lab_form"):
        c1, c2, c3 = st.columns(3)

        with c1:
            market = st.selectbox(
                "Market",
                [
                    "SET",
                    "USA",
                ],
                key="strategy_lab_market",
            )
            symbol = st.text_input(
                "Symbol",
                key="strategy_lab_symbol",
            )

        with c2:
            start_date = st.date_input(
                "Start Date",
                value=default_start,
                key="strategy_lab_start_date",
            )
            end_date = st.date_input(
                "End Date",
                value=today,
                key="strategy_lab_end_date",
            )

        with c3:
            min_score = st.number_input(
                "Min Score",
                min_value=0.0,
                max_value=100.0,
                step=1.0,
                key="strategy_lab_min_score",
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
                key="strategy_lab_enable_stop_loss",
            )
            stop_loss_pct = st.number_input(
                "Stop Loss %",
                min_value=0.0,
                step=0.5,
                key="strategy_lab_stop_loss_pct",
            )

        with r2:
            enable_target = st.checkbox(
                "Target",
                key="strategy_lab_enable_target",
            )
            target_pct = st.number_input(
                "Target %",
                min_value=0.0,
                step=0.5,
                key="strategy_lab_target_pct",
            )

        with r3:
            enable_max_holding_days = st.checkbox(
                "Max Holding Days",
                key="strategy_lab_enable_max_holding_days",
            )
            max_holding_days = st.number_input(
                "Max Days",
                min_value=0,
                step=1,
                key="strategy_lab_max_holding_days",
            )

        with r4:
            enable_trailing_stop = st.checkbox(
                "Trailing Stop",
                key="strategy_lab_enable_trailing_stop",
            )
            trailing_stop_pct = st.number_input(
                "Trailing Stop %",
                min_value=0.0,
                step=0.5,
                key="strategy_lab_trailing_stop_pct",
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

    current_parameters = strategy_lab_parameters_from_values(
        min_score,
        enable_stop_loss,
        stop_loss_pct,
        enable_target,
        target_pct,
        enable_max_holding_days,
        max_holding_days,
        enable_trailing_stop,
        trailing_stop_pct,
    )
    render_preset_comparison(
        current_parameters,
        presets,
    )

    if submitted:
        parameter_errors = validate_parameters(current_parameters)

        if not symbol.strip():
            st.error("Symbol is required")
        elif start_date >= end_date:
            st.error("Start Date must be before End Date")
        elif parameter_errors:
            st.error(" ".join(parameter_errors))
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
    render_optimizer_section()

    st.divider()
    render_strategy_history_dashboard()
