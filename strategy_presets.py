import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd


PRESET_DIR = Path("data") / "presets"
DEFAULT_PRESET_FILE = PRESET_DIR / "default_presets.json"
PRESET_VERSION = "River Alpha Strategy Preset v1"
PARAMETER_LABELS = {
    "min_score": "Min Score",
    "enable_stop_loss": "Stop Loss Enabled",
    "stop_loss_pct": "Stop Loss %",
    "enable_target": "Target Enabled",
    "target_pct": "Target %",
    "enable_trailing_stop": "Trailing Stop Enabled",
    "trailing_stop_pct": "Trailing Stop %",
    "enable_max_holding_days": "Max Holding Enabled",
    "max_holding_days": "Max Holding Days",
}
PERFORMANCE_COLUMNS = [
    "Preset",
    "Stars",
    "WinRate",
    "ProfitFactor",
    "Trades",
    "Runs",
    "Source",
]
DEFAULT_PARAMETERS = {
    "min_score": 70.0,
    "enable_stop_loss": False,
    "stop_loss_pct": 8.0,
    "enable_target": False,
    "target_pct": 20.0,
    "enable_trailing_stop": False,
    "trailing_stop_pct": 10.0,
    "enable_max_holding_days": False,
    "max_holding_days": 20,
}
BUILT_IN_PRESETS = [
    {
        "name": "Conservative",
        "description": "High quality setup with tight risk controls.",
        "min_score": 90,
        "stop_loss_pct": 5,
        "target_pct": 15,
        "trailing_stop_pct": 5,
        "max_holding_days": 30,
    },
    {
        "name": "Swing",
        "description": "Balanced swing trading preset.",
        "min_score": 80,
        "stop_loss_pct": 8,
        "target_pct": 20,
        "trailing_stop_pct": 10,
        "max_holding_days": 60,
    },
    {
        "name": "Momentum",
        "description": "Momentum continuation with wider exits.",
        "min_score": 85,
        "stop_loss_pct": 10,
        "target_pct": 25,
        "trailing_stop_pct": 12,
        "max_holding_days": 45,
    },
    {
        "name": "Breakout",
        "description": "Breakout-focused preset with defined follow-through.",
        "min_score": 88,
        "stop_loss_pct": 7,
        "target_pct": 22,
        "trailing_stop_pct": 10,
        "max_holding_days": 30,
    },
    {
        "name": "Position",
        "description": "Longer holding preset for position trades.",
        "min_score": 75,
        "stop_loss_pct": 12,
        "target_pct": 35,
        "trailing_stop_pct": 15,
        "max_holding_days": 120,
    },
]


def now_string():

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def coerce_bool(value):

    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in (
        "true",
        "1",
        "yes",
        "y",
    )


def ensure_preset_dir():

    PRESET_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


def sanitize_preset_filename(name):

    filename = re.sub(
        r"[^A-Za-z0-9_.-]+",
        "_",
        str(name).strip(),
    ).strip("_")

    return filename or "preset"


def preset_file_path(name):

    return PRESET_DIR / f"{sanitize_preset_filename(name)}.json"


def normalize_parameters(parameters=None):

    source = parameters or {}
    normalized = DEFAULT_PARAMETERS.copy()

    for key in normalized:
        if key in source:
            normalized[key] = source[key]

    normalized["min_score"] = float(normalized["min_score"])
    normalized["enable_stop_loss"] = coerce_bool(
        normalized["enable_stop_loss"]
    )
    normalized["stop_loss_pct"] = float(normalized["stop_loss_pct"])
    normalized["enable_target"] = coerce_bool(normalized["enable_target"])
    normalized["target_pct"] = float(normalized["target_pct"])
    normalized["enable_trailing_stop"] = coerce_bool(
        normalized["enable_trailing_stop"]
    )
    normalized["trailing_stop_pct"] = float(normalized["trailing_stop_pct"])
    normalized["enable_max_holding_days"] = coerce_bool(
        normalized["enable_max_holding_days"]
    )
    normalized["max_holding_days"] = int(
        float(normalized["max_holding_days"])
    )

    return normalized


def validate_parameters(parameters):

    params = normalize_parameters(parameters)
    errors = []

    if params["min_score"] < 0 or params["min_score"] > 100:
        errors.append("Min Score must be between 0 and 100.")

    if params["stop_loss_pct"] < 0:
        errors.append("Stop Loss cannot be negative.")

    if params["target_pct"] < 0:
        errors.append("Target cannot be negative.")

    if (
        params["target_pct"] > 0
        and params["stop_loss_pct"] > 0
        and params["target_pct"] <= params["stop_loss_pct"]
    ):
        errors.append("Target must be greater than Stop Loss.")

    if params["trailing_stop_pct"] < 0:
        errors.append("Trailing Stop cannot be negative.")

    if params["max_holding_days"] < 0:
        errors.append("Max Holding Days cannot be negative.")

    if params["enable_max_holding_days"] and params["max_holding_days"] <= 0:
        errors.append("Max Holding Days must be greater than 0 when enabled.")

    return errors


def preset_dict(
    name,
    description,
    author,
    parameters,
    version=PRESET_VERSION,
    created_date=None,
    modified_date=None,
):

    clean_name = str(name).strip()

    if not clean_name:
        raise ValueError("Preset Name is required.")

    params = normalize_parameters(parameters)
    errors = validate_parameters(params)

    if errors:
        raise ValueError(" ".join(errors))

    return {
        "Name": clean_name,
        "Description": str(description or "").strip(),
        "Version": str(version or PRESET_VERSION).strip(),
        "CreatedDate": created_date or now_string(),
        "ModifiedDate": modified_date or now_string(),
        "Author": str(author or "River Alpha").strip(),
        "Parameters": params,
    }


def built_in_preset_rows():

    rows = []

    for preset in BUILT_IN_PRESETS:
        parameters = {
            "min_score": preset["min_score"],
            "enable_stop_loss": True,
            "stop_loss_pct": preset["stop_loss_pct"],
            "enable_target": True,
            "target_pct": preset["target_pct"],
            "enable_trailing_stop": True,
            "trailing_stop_pct": preset["trailing_stop_pct"],
            "enable_max_holding_days": True,
            "max_holding_days": preset["max_holding_days"],
        }
        rows.append(
            preset_dict(
                name=preset["name"],
                description=preset["description"],
                author="River Alpha",
                parameters=parameters,
                created_date="2026-07-07 00:00:00",
                modified_date="2026-07-07 00:00:00",
            )
        )

    return rows


def reset_default_presets():

    ensure_preset_dir()
    payload = {
        "Presets": built_in_preset_rows(),
    }
    DEFAULT_PRESET_FILE.write_text(
        json.dumps(
            payload,
            indent=2,
        ),
        encoding="utf-8",
    )

    return DEFAULT_PRESET_FILE


def ensure_default_presets():

    ensure_preset_dir()

    if not DEFAULT_PRESET_FILE.exists():
        reset_default_presets()


def load_preset_file(path):

    try:
        payload = json.loads(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        return []

    if isinstance(payload, dict) and "Presets" in payload:
        presets = payload.get("Presets", [])
    else:
        presets = [
            payload,
        ]

    rows = []

    for preset in presets:
        if not isinstance(preset, dict):
            continue

        name = preset.get("Name", "").strip()

        if not name:
            continue

        try:
            rows.append(
                preset_dict(
                    name=name,
                    description=preset.get("Description", ""),
                    author=preset.get("Author", "River Alpha"),
                    parameters=preset.get("Parameters", {}),
                    version=preset.get("Version", PRESET_VERSION),
                    created_date=preset.get("CreatedDate"),
                    modified_date=preset.get("ModifiedDate"),
                )
            )
        except ValueError:
            continue

    return rows


def load_presets():

    ensure_default_presets()
    presets = {}

    for preset in load_preset_file(DEFAULT_PRESET_FILE):
        preset["_Source"] = str(DEFAULT_PRESET_FILE)
        preset["_BuiltIn"] = True
        presets[preset["Name"]] = preset

    for path in sorted(PRESET_DIR.glob("*.json")):
        if path == DEFAULT_PRESET_FILE:
            continue

        for preset in load_preset_file(path):
            preset["_Source"] = str(path)
            preset["_BuiltIn"] = False
            presets[preset["Name"]] = preset

    return dict(
        sorted(
            presets.items(),
            key=lambda item: item[0].lower(),
        )
    )


def load_preset(name):

    return load_presets().get(name)


def save_preset(
    name,
    description,
    author,
    parameters,
    version=PRESET_VERSION,
):

    ensure_default_presets()
    existing = load_preset(name)
    created_date = (
        existing.get("CreatedDate")
        if existing
        else now_string()
    )
    preset = preset_dict(
        name=name,
        description=description,
        author=author,
        parameters=parameters,
        version=version,
        created_date=created_date,
        modified_date=now_string(),
    )
    path = preset_file_path(name)
    path.write_text(
        json.dumps(
            preset,
            indent=2,
        ),
        encoding="utf-8",
    )

    return path


def delete_preset(name):

    preset = load_preset(name)

    if not preset:
        return False, "Preset not found."

    path = Path(preset.get("_Source", ""))

    if preset.get("_BuiltIn") or path == DEFAULT_PRESET_FILE:
        return False, "Built-in presets cannot be deleted. Use Reset instead."

    if path.exists():
        path.unlink()
        return True, f"Deleted {name}."

    return False, "Preset file not found."


def export_preset_json(preset):

    clean = {
        key: value
        for key, value in preset.items()
        if not key.startswith("_")
    }

    return json.dumps(
        clean,
        indent=2,
    )


def import_preset_json(json_text):

    payload = json.loads(json_text)

    if isinstance(payload, dict) and "Presets" in payload:
        saved = []

        for preset in payload.get("Presets", []):
            saved.append(
                save_preset(
                    name=preset.get("Name", ""),
                    description=preset.get("Description", ""),
                    author=preset.get("Author", "Imported"),
                    parameters=preset.get("Parameters", {}),
                    version=preset.get("Version", PRESET_VERSION),
                )
            )

        return saved

    return [
        save_preset(
            name=payload.get("Name", ""),
            description=payload.get("Description", ""),
            author=payload.get("Author", "Imported"),
            parameters=payload.get("Parameters", {}),
            version=payload.get("Version", PRESET_VERSION),
        )
    ]


def compare_parameters(current_parameters, preset_parameters):

    current = normalize_parameters(current_parameters)
    preset = normalize_parameters(preset_parameters)
    rows = []

    for key, label in PARAMETER_LABELS.items():
        current_value = current.get(key)
        preset_value = preset.get(key)
        changed = current_value != preset_value
        rows.append({
            "Parameter": label,
            "Current": current_value,
            "Preset": preset_value,
            "Changed": changed,
        })

    return pd.DataFrame(rows)


def as_bool(value):

    return coerce_bool(value)


def numeric_series(df, column):

    if column not in df.columns:
        return pd.Series(
            0,
            index=df.index,
            dtype="float64",
        )

    return pd.to_numeric(
        df[column],
        errors="coerce",
    ).fillna(0)


def numeric_match(series, value, tolerance=0.0001):

    return (
        pd.to_numeric(
            series,
            errors="coerce",
        ).fillna(-999999)
        - float(value)
    ).abs() <= tolerance


def strategy_history_matches(history, parameters):

    if history is None or history.empty:
        return pd.DataFrame()

    params = normalize_parameters(parameters)
    required = [
        "MinScore",
        "StopLossEnabled",
        "StopLossPct",
        "TargetEnabled",
        "TargetPct",
        "TrailingEnabled",
        "TrailingPct",
        "MaxHoldingEnabled",
        "MaxHoldingDays",
    ]

    if any(column not in history.columns for column in required):
        return pd.DataFrame()

    mask = (
        numeric_match(history["MinScore"], params["min_score"])
        & (history["StopLossEnabled"].map(as_bool) == params["enable_stop_loss"])
        & numeric_match(history["StopLossPct"], params["stop_loss_pct"])
        & (history["TargetEnabled"].map(as_bool) == params["enable_target"])
        & numeric_match(history["TargetPct"], params["target_pct"])
        & (history["TrailingEnabled"].map(as_bool) == params["enable_trailing_stop"])
        & numeric_match(history["TrailingPct"], params["trailing_stop_pct"])
        & (
            history["MaxHoldingEnabled"].map(as_bool)
            == params["enable_max_holding_days"]
        )
        & numeric_match(history["MaxHoldingDays"], params["max_holding_days"])
    )

    return history[mask].copy()


def optimizer_matches(optimizer_results, parameters):

    if optimizer_results is None or optimizer_results.empty:
        return pd.DataFrame()

    params = normalize_parameters(parameters)
    required = [
        "MinScore",
        "StopLossPct",
        "TargetPct",
        "MaxHoldingDays",
        "TrailingStopPct",
    ]

    if any(column not in optimizer_results.columns for column in required):
        return pd.DataFrame()

    mask = (
        numeric_match(optimizer_results["MinScore"], params["min_score"])
        & numeric_match(optimizer_results["StopLossPct"], params["stop_loss_pct"])
        & numeric_match(optimizer_results["TargetPct"], params["target_pct"])
        & numeric_match(
            optimizer_results["MaxHoldingDays"],
            params["max_holding_days"],
        )
        & numeric_match(
            optimizer_results["TrailingStopPct"],
            params["trailing_stop_pct"],
        )
    )

    return optimizer_results[mask].copy()


def stars_from_performance(win_rate, profit_factor, trades):

    if int(trades or 0) <= 0:
        return "No test data"

    win_rate = float(win_rate or 0)
    profit_factor = float(profit_factor or 0)

    if win_rate >= 70 and profit_factor >= 2.5:
        stars = 5
    elif win_rate >= 60 and profit_factor >= 2.0:
        stars = 4
    elif win_rate >= 55 and profit_factor >= 1.5:
        stars = 3
    elif win_rate >= 50 and profit_factor >= 1.1:
        stars = 2
    else:
        stars = 1

    return "★" * stars + "☆" * (5 - stars)


def performance_from_strategy_history(preset, history):

    matches = strategy_history_matches(
        history,
        preset.get("Parameters", {}),
    )

    if matches.empty:
        return None

    trades = numeric_series(
        matches,
        "TotalTrades",
    )
    winning_trades = numeric_series(
        matches,
        "WinningTrades",
    )
    total_trades = int(trades.sum())

    if total_trades > 0 and "WinningTrades" in matches.columns:
        win_rate = winning_trades.sum() / total_trades * 100
    else:
        win_rate = numeric_series(
            matches,
            "WinRate",
        ).mean()

    profit_factor = numeric_series(
        matches,
        "ProfitFactor",
    ).mean()

    return {
        "Preset": preset["Name"],
        "Stars": stars_from_performance(
            win_rate,
            profit_factor,
            total_trades,
        ),
        "WinRate": round(float(win_rate or 0), 2),
        "ProfitFactor": round(float(profit_factor or 0), 2),
        "Trades": total_trades,
        "Runs": int(len(matches)),
        "Source": "Strategy History",
    }


def performance_from_optimizer(preset, optimizer_results):

    matches = optimizer_matches(
        optimizer_results,
        preset.get("Parameters", {}),
    )

    if matches.empty:
        return None

    trades = numeric_series(
        matches,
        "TotalTrades",
    )
    total_trades = int(trades.sum())
    win_rate = numeric_series(
        matches,
        "WinRate",
    ).mean()
    profit_factor = numeric_series(
        matches,
        "ProfitFactor",
    ).mean()

    return {
        "Preset": preset["Name"],
        "Stars": stars_from_performance(
            win_rate,
            profit_factor,
            total_trades,
        ),
        "WinRate": round(float(win_rate or 0), 2),
        "ProfitFactor": round(float(profit_factor or 0), 2),
        "Trades": total_trades,
        "Runs": int(len(matches)),
        "Source": "Optimizer Results",
    }


def preset_performance(preset, history=None, optimizer_results=None):

    performance = performance_from_strategy_history(
        preset,
        history,
    )

    if performance:
        return performance

    performance = performance_from_optimizer(
        preset,
        optimizer_results,
    )

    if performance:
        return performance

    return {
        "Preset": preset["Name"],
        "Stars": "No test data",
        "WinRate": 0,
        "ProfitFactor": 0,
        "Trades": 0,
        "Runs": 0,
        "Source": "No matching results",
    }


def build_preset_performance_table(
    presets,
    history=None,
    optimizer_results=None,
):

    rows = [
        preset_performance(
            preset,
            history,
            optimizer_results,
        )
        for preset in presets.values()
    ]

    return pd.DataFrame(
        rows,
        columns=PERFORMANCE_COLUMNS,
    )


def parameters_from_optimizer_row(row):

    return normalize_parameters({
        "min_score": row.get("MinScore", 0),
        "enable_stop_loss": float(row.get("StopLossPct", 0) or 0) > 0,
        "stop_loss_pct": row.get("StopLossPct", 0),
        "enable_target": float(row.get("TargetPct", 0) or 0) > 0,
        "target_pct": row.get("TargetPct", 0),
        "enable_trailing_stop": float(row.get("TrailingStopPct", 0) or 0) > 0,
        "trailing_stop_pct": row.get("TrailingStopPct", 0),
        "enable_max_holding_days": int(row.get("MaxHoldingDays", 0) or 0) > 0,
        "max_holding_days": row.get("MaxHoldingDays", 0),
    })
