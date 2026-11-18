"""Dataset loading with encoding fallback and column-name normalisation."""

from __future__ import annotations

import io
import re
from pathlib import Path

import pandas as pd


class DataLoadError(ValueError):
    """Raised when a dataset cannot be read or is unusable."""


def normalize_columns(columns) -> list[str]:
    """snake_case, ASCII-safe, de-duplicated column names."""
    seen: dict[str, int] = {}
    result: list[str] = []
    for i, col in enumerate(columns):
        name = re.sub(r"[^0-9a-zA-Z]+", "_", str(col).strip().lower()).strip("_") or f"column_{i}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        result.append(name)
    return result


def load_dataset(source) -> pd.DataFrame:
    """Load a CSV from a path, bytes, file-like object or DataFrame."""
    if isinstance(source, pd.DataFrame):
        df = source.copy()
    else:
        if isinstance(source, (str, Path)):
            path = Path(source)
            if not path.exists():
                raise DataLoadError(f"Dataset not found: {path}")
            buffer_factory = lambda: path  # noqa: E731
        elif isinstance(source, (bytes, bytearray)):
            buffer_factory = lambda: io.BytesIO(bytes(source))  # noqa: E731
        elif hasattr(source, "read"):
            raw = source.read()
            buffer_factory = lambda: io.BytesIO(raw if isinstance(raw, bytes) else raw.encode())  # noqa: E731
        else:
            raise DataLoadError(f"Unsupported data source type: {type(source).__name__}")

        df = None
        last_error: Exception | None = None
        for encoding in ("utf-8-sig", "latin-1"):
            try:
                df = pd.read_csv(buffer_factory(), encoding=encoding)
                break
            except UnicodeDecodeError as exc:
                last_error = exc
            except (pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
                raise DataLoadError(f"Could not parse the CSV file: {exc}") from exc
        if df is None:
            raise DataLoadError(f"Could not decode the file: {last_error}")

    if df.shape[1] == 0 or df.empty:
        raise DataLoadError("The dataset is empty.")

    df.columns = normalize_columns(df.columns)
    return df.reset_index(drop=True)
