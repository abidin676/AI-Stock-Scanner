from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd

from config import MAX_FRESH_CROSS_DAYS


FRESH_CROSS_COLUMNS = [
    "FreshCrossEligible",
    "IsFreshEMA9Cross",
    "FreshCrossAge",
    "CrossAgeLabel",
    "FreshCrossStatus",
    "FreshCrossStatusLabel",
    "FreshCrossReason",
]


@dataclass(frozen=True)
class FreshCrossResult:
    eligible: bool
    ema9_above_ema20: bool
    age: int | None
    age_label: str
    status: str
    status_label: str
    reason: str


def _value(row: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name not in row:
            continue
        value = row.get(name)
        try:
            if pd.isna(value):
                continue
        except (TypeError, ValueError):
            pass
        if value is not None:
            return value
    return None


def _number_or_none(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().upper() in {
        "TRUE",
        "YES",
        "Y",
        "1",
    }


def cross_age_label(value: Any) -> str:
    age = _number_or_none(value)
    if age is None or age < 0 or not age.is_integer():
        return "-"
    age_value = int(age)
    return "Today" if age_value == 0 else f"{age_value}D"


def fresh_cross_reason_for_age(value: Any) -> str:
    label = cross_age_label(value)
    if label == "Today":
        return "EMA9 เพิ่งตัด EMA20 วันนี้"
    if label == "1D":
        return "EMA9 ตัด EMA20 เมื่อ 1 วันก่อน"
    if label == "2D":
        return "EMA9 ตัด EMA20 เมื่อ 2 วันก่อน"
    if label.endswith("D"):
        return f"EMA9 ตัด EMA20 เมื่อ {label[:-1]} วันก่อน"
    return ""


def evaluate_fresh_cross_policy(
    candidate: pd.Series | Mapping[str, Any],
) -> FreshCrossResult:
    row = candidate.to_dict() if isinstance(candidate, pd.Series) else candidate
    ema9 = _number_or_none(_value(row, "EMA9", "ema9"))
    ema20 = _number_or_none(_value(row, "EMA20", "ema20"))
    age_number = _number_or_none(
        _value(
            row,
            "DaysSinceEMA9CrossEMA20",
            "DaysSinceEMACross",
            "days_since_ema9_cross_ema20",
        )
    )

    if ema9 is not None and ema20 is not None:
        ema9_above_ema20 = ema9 > ema20
    else:
        ema9_above_ema20 = _bool(_value(row, "EMA9AboveEMA20"))

    age = None
    if (
        age_number is not None
        and age_number >= 0
        and age_number.is_integer()
    ):
        age = int(age_number)

    eligible = (
        ema9_above_ema20
        and age is not None
        and age <= MAX_FRESH_CROSS_DAYS
    )

    if age is None:
        status = "NO_CROSS"
        status_label = "ยังไม่ Cross"
        reason = "ยังไม่มีประวัติ EMA9 ตัด EMA20"
    elif not ema9_above_ema20:
        status = "EMA9_NOT_ABOVE"
        status_label = "EMA9 ต่ำกว่า EMA20"
        reason = "รอ EMA9 ตัดขึ้นเหนือ EMA20"
    elif age > MAX_FRESH_CROSS_DAYS:
        status = "STALE_CROSS"
        status_label = "Cross เก่า"
        reason = f"EMA9 Cross เกิน {MAX_FRESH_CROSS_DAYS} วันทำการแล้ว"
    else:
        status = "FRESH_CROSS"
        status_label = "Fresh Cross"
        reason = fresh_cross_reason_for_age(age)

    return FreshCrossResult(
        eligible=bool(eligible),
        ema9_above_ema20=bool(ema9_above_ema20),
        age=age,
        age_label=cross_age_label(age),
        status=status,
        status_label=status_label,
        reason=reason,
    )


def apply_fresh_cross_policy(dataframe: pd.DataFrame | None) -> pd.DataFrame:
    if dataframe is None:
        return pd.DataFrame(columns=FRESH_CROSS_COLUMNS)

    data = dataframe.copy()
    if data.empty:
        for column in FRESH_CROSS_COLUMNS:
            if column not in data.columns:
                data[column] = pd.Series(dtype="object")
        return data

    results = [
        evaluate_fresh_cross_policy(row)
        for _, row in data.iterrows()
    ]
    data["FreshCrossEligible"] = [result.eligible for result in results]
    data["IsFreshEMA9Cross"] = data["FreshCrossEligible"]
    data["FreshCrossAge"] = [result.age for result in results]
    data["CrossAgeLabel"] = [result.age_label for result in results]
    data["FreshCrossStatus"] = [result.status for result in results]
    data["FreshCrossStatusLabel"] = [
        result.status_label
        for result in results
    ]
    data["FreshCrossReason"] = [result.reason for result in results]
    return data
