from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
import json
import uuid

import pandas as pd


def temp_path_for(path: Path) -> Path:
    path = Path(path)
    token = uuid.uuid4().hex[:10]
    return path.with_name(f".{path.stem}.{token}.tmp{path.suffix}")


def atomic_write_csv(df: pd.DataFrame, path: str | Path, **kwargs) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = temp_path_for(path)
    df.to_csv(tmp_path, **kwargs)
    tmp_path.replace(path)
    return path


def atomic_write_excel(df: pd.DataFrame, path: str | Path, **kwargs) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = temp_path_for(path)
    df.to_excel(tmp_path, **kwargs)
    tmp_path.replace(path)
    return path


def atomic_write_json(data: Mapping[str, Any], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = temp_path_for(path)
    tmp_path.write_text(
        json.dumps(dict(data), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    tmp_path.replace(path)
    return path
