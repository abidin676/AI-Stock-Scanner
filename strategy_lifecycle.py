from datetime import date, datetime
from pathlib import Path

import pandas as pd


LIFECYCLE_FILE = Path("data") / "strategy_lifecycle.csv"

LIFECYCLE_STATES = [
    "EARLY",
    "BREAKOUT",
    "MOMENTUM",
    "EXTENDED",
    "WATCH",
    "SKIP",
    "UNKNOWN",
]

LIFECYCLE_COLUMNS = [
    "Symbol",
    "Market",
    "PreviousState",
    "CurrentState",
    "FirstSeenDate",
    "LastSeenDate",
    "StateChangedDate",
    "DaysInState",
    "StateChanged",
    "PreviousStrategyMode",
    "CurrentStrategyMode",
    "PreviousStrategySignal",
    "CurrentStrategySignal",
    "PreviousStrategyScore",
    "CurrentStrategyScore",
    "PreviousSetup",
    "CurrentSetup",
]

SCAN_LIFECYCLE_COLUMNS = [
    "LifecycleState",
    "PreviousLifecycleState",
    "DaysInState",
    "StateChanged",
]

TRANSITION_COLUMNS = [
    "Symbol",
    "Market",
    "PreviousState",
    "CurrentState",
    "StateChangedDate",
    "DaysInState",
    "CurrentStrategyScore",
    "CurrentSetup",
]


def _today_iso(today=None):

    if today is None:
        return date.today().isoformat()

    if isinstance(today, datetime):
        return today.date().isoformat()

    if isinstance(today, date):
        return today.isoformat()

    return str(today)[:10]


def _safe_float(value, default=0.0):

    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_text(value, default=""):

    if value is None or pd.isna(value):
        return default

    return str(value)


def _normalize_bool(value):

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value != 0

    return str(value).strip().upper() in {
        "TRUE",
        "1",
        "YES",
        "Y",
    }


def normalize_strategy_mode(value):

    mode = _safe_text(value, "Standard").strip().lower()

    if "early" in mode:
        return "Early"

    if "breakout" in mode:
        return "Breakout"

    if "momentum" in mode:
        return "Momentum"

    return "Standard"


def _normalize_state(value):

    state = _safe_text(value, "UNKNOWN").strip().upper()

    if state in LIFECYCLE_STATES:
        return state

    return "UNKNOWN"


def _normalize_signal(value):

    return _safe_text(value).strip().upper()


def _normalize_setup(value):

    return _safe_text(value).strip()


def _parse_date(value):

    parsed = pd.to_datetime(
        value,
        errors="coerce",
    )

    if pd.isna(parsed):
        return None

    return parsed.date()


def calculate_days_in_state(state_changed_date, today=None):

    if isinstance(state_changed_date, pd.Series):
        return state_changed_date.apply(
            lambda value: calculate_days_in_state(
                value,
                today=today,
            )
        )

    start_date = _parse_date(state_changed_date)
    end_date = _parse_date(
        _today_iso(today)
    )

    if start_date is None or end_date is None:
        return 0

    return max(
        0,
        (end_date - start_date).days,
    )


def ensure_lifecycle_columns(df):

    data = df.copy()
    numeric_columns = {
        "DaysInState",
        "PreviousStrategyScore",
        "CurrentStrategyScore",
    }

    for column in LIFECYCLE_COLUMNS:
        if column not in data.columns:
            data[column] = 0 if column in numeric_columns else ""

    data = data[LIFECYCLE_COLUMNS]

    data["Symbol"] = (
        data["Symbol"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )
    data["Market"] = (
        data["Market"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )
    data["PreviousState"] = data["PreviousState"].apply(
        _normalize_state
    )
    data["CurrentState"] = data["CurrentState"].apply(
        _normalize_state
    )
    data["DaysInState"] = pd.to_numeric(
        data["DaysInState"],
        errors="coerce",
    ).fillna(0).astype(int)
    data["StateChanged"] = data["StateChanged"].apply(
        _normalize_bool
    )

    for column in (
        "PreviousStrategyScore",
        "CurrentStrategyScore",
    ):
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        ).fillna(0).astype(float)

    return data


def load_lifecycle(path=LIFECYCLE_FILE):

    path = Path(path)
    path.parent.mkdir(
        exist_ok=True
    )

    if not path.exists():
        lifecycle = pd.DataFrame(
            columns=LIFECYCLE_COLUMNS
        )
        save_lifecycle(
            lifecycle,
            path=path,
        )
        return lifecycle

    try:
        lifecycle = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        lifecycle = pd.DataFrame(
            columns=LIFECYCLE_COLUMNS
        )

    lifecycle = ensure_lifecycle_columns(lifecycle)
    save_lifecycle(
        lifecycle,
        path=path,
    )

    return lifecycle


def save_lifecycle(df, path=LIFECYCLE_FILE):

    path = Path(path)
    path.parent.mkdir(
        exist_ok=True
    )
    lifecycle = ensure_lifecycle_columns(df)
    lifecycle.to_csv(
        path,
        index=False,
    )

    return path


def ensure_scan_strategy_columns(scanner_df, strategy_mode="standard"):

    data = scanner_df.copy()
    mode_label = normalize_strategy_mode(strategy_mode)

    if "Symbol" not in data.columns:
        data["Symbol"] = ""

    if "Market" not in data.columns:
        data["Market"] = ""

    if "Signal" not in data.columns:
        data["Signal"] = ""

    if "Setup" not in data.columns:
        data["Setup"] = ""

    if "Score" not in data.columns:
        data["Score"] = 0

    if "StrategyMode" not in data.columns:
        data["StrategyMode"] = mode_label

    if "StrategySignal" not in data.columns:
        data["StrategySignal"] = data["Signal"]

    if "StrategyScore" not in data.columns:
        data["StrategyScore"] = data["Score"]

    if "StrategySetup" not in data.columns:
        data["StrategySetup"] = data["Setup"]

    data["Symbol"] = (
        data["Symbol"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )
    data["Market"] = (
        data["Market"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )
    data["StrategyMode"] = (
        data["StrategyMode"]
        .fillna("")
        .astype(str)
        .replace("", mode_label)
        .apply(normalize_strategy_mode)
    )
    data["StrategyScore"] = pd.to_numeric(
        data["StrategyScore"],
        errors="coerce",
    ).fillna(0).astype(float)

    return data


def map_to_lifecycle_state(row):

    mode = normalize_strategy_mode(
        row.get(
            "StrategyMode",
            "Standard",
        )
    )
    signal = _normalize_signal(
        row.get(
            "StrategySignal",
            row.get(
                "Signal",
                "",
            ),
        )
    )

    if "EXTENDED" in signal:
        return "EXTENDED"

    if "SKIP" in signal:
        return "SKIP"

    if mode == "Early":
        if "BUY" in signal or "WATCH" in signal or "EARLY" in signal:
            return "EARLY"
        return "UNKNOWN"

    if mode == "Breakout":
        if "BREAKOUT" in signal and (
            "BUY" in signal or "WATCH" in signal
        ):
            return "BREAKOUT"
        return "UNKNOWN"

    if mode == "Momentum":
        if "MOMENTUM" in signal and (
            "BUY" in signal or "WATCH" in signal
        ):
            return "MOMENTUM"
        return "UNKNOWN"

    if "BUY" in signal or "WATCH" in signal or "EARLY" in signal:
        return "WATCH"

    if not signal or "NO DATA" in signal:
        return "UNKNOWN"

    return "UNKNOWN"


def _scan_values(row):

    return {
        "CurrentStrategyMode": normalize_strategy_mode(
            row.get(
                "StrategyMode",
                "Standard",
            )
        ),
        "CurrentStrategySignal": _safe_text(
            row.get(
                "StrategySignal",
                row.get(
                    "Signal",
                    "",
                ),
            )
        ),
        "CurrentStrategyScore": _safe_float(
            row.get(
                "StrategyScore",
                row.get(
                    "Score",
                    0,
                ),
            )
        ),
        "CurrentSetup": _normalize_setup(
            row.get(
                "StrategySetup",
                row.get(
                    "Setup",
                    "",
                ),
            )
        ),
    }


def _new_lifecycle_row(row, current_state, today):

    values = _scan_values(row)

    return {
        "Symbol": row["Symbol"],
        "Market": row["Market"],
        "PreviousState": "UNKNOWN",
        "CurrentState": current_state,
        "FirstSeenDate": today,
        "LastSeenDate": today,
        "StateChangedDate": today,
        "DaysInState": 0,
        "StateChanged": True,
        "PreviousStrategyMode": "Standard",
        "CurrentStrategyMode": values["CurrentStrategyMode"],
        "PreviousStrategySignal": "",
        "CurrentStrategySignal": values["CurrentStrategySignal"],
        "PreviousStrategyScore": 0,
        "CurrentStrategyScore": values["CurrentStrategyScore"],
        "PreviousSetup": "",
        "CurrentSetup": values["CurrentSetup"],
    }


def _updated_lifecycle_row(existing_row, scan_row, current_state, today):

    existing = existing_row.to_dict()
    values = _scan_values(scan_row)
    previous_current_state = _normalize_state(
        existing.get(
            "CurrentState",
            "UNKNOWN",
        )
    )
    state_changed = previous_current_state != current_state

    if state_changed:
        return {
            "Symbol": scan_row["Symbol"],
            "Market": scan_row["Market"],
            "PreviousState": previous_current_state,
            "CurrentState": current_state,
            "FirstSeenDate": existing.get(
                "FirstSeenDate",
                today,
            )
            or today,
            "LastSeenDate": today,
            "StateChangedDate": today,
            "DaysInState": 0,
            "StateChanged": True,
            "PreviousStrategyMode": existing.get(
                "CurrentStrategyMode",
                "Standard",
            ),
            "CurrentStrategyMode": values["CurrentStrategyMode"],
            "PreviousStrategySignal": existing.get(
                "CurrentStrategySignal",
                "",
            ),
            "CurrentStrategySignal": values["CurrentStrategySignal"],
            "PreviousStrategyScore": _safe_float(
                existing.get(
                    "CurrentStrategyScore",
                    0,
                )
            ),
            "CurrentStrategyScore": values["CurrentStrategyScore"],
            "PreviousSetup": existing.get(
                "CurrentSetup",
                "",
            ),
            "CurrentSetup": values["CurrentSetup"],
        }

    state_changed_date = existing.get(
        "StateChangedDate",
        today,
    ) or today

    return {
        "Symbol": scan_row["Symbol"],
        "Market": scan_row["Market"],
        "PreviousState": existing.get(
            "PreviousState",
            "UNKNOWN",
        ),
        "CurrentState": current_state,
        "FirstSeenDate": existing.get(
            "FirstSeenDate",
            today,
        )
        or today,
        "LastSeenDate": today,
        "StateChangedDate": state_changed_date,
        "DaysInState": calculate_days_in_state(
            state_changed_date,
            today=today,
        ),
        "StateChanged": False,
        "PreviousStrategyMode": existing.get(
            "PreviousStrategyMode",
            "Standard",
        ),
        "CurrentStrategyMode": values["CurrentStrategyMode"],
        "PreviousStrategySignal": existing.get(
            "PreviousStrategySignal",
            "",
        ),
        "CurrentStrategySignal": values["CurrentStrategySignal"],
        "PreviousStrategyScore": _safe_float(
            existing.get(
                "PreviousStrategyScore",
                0,
            )
        ),
        "CurrentStrategyScore": values["CurrentStrategyScore"],
        "PreviousSetup": existing.get(
            "PreviousSetup",
            "",
        ),
        "CurrentSetup": values["CurrentSetup"],
    }


def update_lifecycle_from_scan(scanner_df, strategy_mode="standard", today=None):

    if scanner_df is None:
        return pd.DataFrame()

    data = ensure_scan_strategy_columns(
        scanner_df,
        strategy_mode=strategy_mode,
    )

    if data.empty:
        save_lifecycle(
            load_lifecycle()
        )
        return data

    today = _today_iso(today)
    lifecycle = load_lifecycle()
    lifecycle = lifecycle.drop_duplicates(
        subset=[
            "Symbol",
            "Market",
        ],
        keep="last",
    )
    existing_lookup = lifecycle.set_index(
        [
            "Symbol",
            "Market",
        ],
        drop=False,
    )
    updated_rows = []
    updated_keys = set()

    for _, row in data.iterrows():
        symbol = row["Symbol"]
        market = row["Market"]

        if not symbol or not market:
            continue

        key = (
            symbol,
            market,
        )
        current_state = map_to_lifecycle_state(row)

        if key in existing_lookup.index:
            lifecycle_row = _updated_lifecycle_row(
                existing_lookup.loc[key],
                row,
                current_state,
                today,
            )
        else:
            lifecycle_row = _new_lifecycle_row(
                row,
                current_state,
                today,
            )

        updated_rows.append(lifecycle_row)
        updated_keys.add(key)

    updated = ensure_lifecycle_columns(
        pd.DataFrame(
            updated_rows,
            columns=LIFECYCLE_COLUMNS,
        )
    )

    if lifecycle.empty:
        combined = updated
    else:
        keep_mask = ~lifecycle.apply(
            lambda row: (
                row["Symbol"],
                row["Market"],
            )
            in updated_keys,
            axis=1,
        )
        combined = pd.concat(
            [
                lifecycle[keep_mask],
                updated,
            ],
            ignore_index=True,
        )

    save_lifecycle(combined)

    scan_lifecycle = updated[
        [
            "Symbol",
            "Market",
            "CurrentState",
            "PreviousState",
            "DaysInState",
            "StateChanged",
        ]
    ].rename(
        columns={
            "CurrentState": "LifecycleState",
            "PreviousState": "PreviousLifecycleState",
        }
    )

    data = data.drop(
        columns=[
            column
            for column in SCAN_LIFECYCLE_COLUMNS
            if column in data.columns
        ],
        errors="ignore",
    )
    data = data.merge(
        scan_lifecycle,
        on=[
            "Symbol",
            "Market",
        ],
        how="left",
    )
    data["LifecycleState"] = data["LifecycleState"].fillna("UNKNOWN")
    data["PreviousLifecycleState"] = (
        data["PreviousLifecycleState"].fillna("UNKNOWN")
    )
    data["DaysInState"] = pd.to_numeric(
        data["DaysInState"],
        errors="coerce",
    ).fillna(0).astype(int)
    data["StateChanged"] = data["StateChanged"].apply(
        _normalize_bool
    )

    return data


def get_state_transitions(limit=50):

    lifecycle = load_lifecycle()

    if lifecycle.empty:
        return pd.DataFrame(
            columns=TRANSITION_COLUMNS
        )

    transitions = lifecycle[
        (lifecycle["PreviousState"] != lifecycle["CurrentState"])
        &
        (lifecycle["PreviousState"] != "UNKNOWN")
    ].copy()

    if transitions.empty:
        return pd.DataFrame(
            columns=TRANSITION_COLUMNS
        )

    transitions["_changed_at"] = pd.to_datetime(
        transitions["StateChangedDate"],
        errors="coerce",
    )
    transitions = transitions.sort_values(
        [
            "_changed_at",
            "Symbol",
        ],
        ascending=[
            False,
            True,
        ],
        na_position="last",
    )

    if limit:
        transitions = transitions.head(limit)

    return transitions[TRANSITION_COLUMNS]


def get_new_stage_candidates(states=None):

    lifecycle = load_lifecycle()

    if lifecycle.empty:
        return pd.DataFrame(
            columns=LIFECYCLE_COLUMNS
        )

    states = states or [
        "EARLY",
        "BREAKOUT",
        "MOMENTUM",
    ]
    states = {
        _normalize_state(state)
        for state in states
    }

    return lifecycle[
        lifecycle["StateChanged"]
        &
        lifecycle["CurrentState"].isin(states)
    ].copy()
