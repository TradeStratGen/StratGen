import math
import re
from typing import Any


INDICATOR_NAMESPACE_COLUMNS = (
    "Close",
    "SMA_20",
    "SMA_50",
    "RSI",
    "RSI2",
    "MACD_hist",
    "ATR_pct",
)

OPTIONAL_NAMESPACE_COLUMNS = (
    "volatility",
    "returns",
)

_WARNED_MESSAGES: set[str] = set()


def _warn_once(message: str):
    if message in _WARNED_MESSAGES:
        return
    _WARNED_MESSAGES.add(message)
    print(message)


def _is_missing_number(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return False


def validate_indicator_dataframe(df, context: str = "system"):
    if df is None or len(df) == 0:
        raise ValueError(f"[{context}] Empty dataframe; cannot evaluate strategies")

    missing_columns = [col for col in INDICATOR_NAMESPACE_COLUMNS if col not in df.columns]
    if missing_columns:
        raise ValueError(
            f"[{context}] Missing required indicator columns: {', '.join(sorted(missing_columns))}"
        )

    bad_rows = df[list(INDICATOR_NAMESPACE_COLUMNS)].isna().any(axis=1)
    if bool(bad_rows.any()):
        bad_count = int(bad_rows.sum())
        raise ValueError(
            f"[{context}] Found {bad_count} rows with missing required indicators (including ATR_pct); aborting evaluation"
        )


def build_indicator_namespace(row, context: str = "system", strict: bool = True, warn_missing_columns: bool = False) -> dict:
    ns = {}
    missing_cols = []

    cols = INDICATOR_NAMESPACE_COLUMNS + OPTIONAL_NAMESPACE_COLUMNS
    for col in cols:
        raw = row.get(col) if hasattr(row, "get") else None
        try:
            value = float(raw)
        except Exception:
            value = None

        if _is_missing_number(value):
            if col in INDICATOR_NAMESPACE_COLUMNS:
                missing_cols.append(col)
            continue
        ns[col] = value

    if missing_cols and strict:
        raise ValueError(
            f"[{context}] Missing required indicators in row: {', '.join(sorted(missing_cols))}"
        )

    if warn_missing_columns and missing_cols:
        _warn_once(
            f"[Namespace] [{context}] Missing indicators in row: {', '.join(sorted(missing_cols))}"
        )

    return ns


def _extract_identifiers(expr: str) -> set[str]:
    tokens = set(re.findall(r"\b[A-Za-z_]\w*\b", str(expr)))
    ignore = {
        "and",
        "or",
        "not",
        "True",
        "False",
    }
    return {t for t in tokens if t not in ignore}


def evaluate_expression(expr: str, namespace: dict, context: str = "system") -> bool:
    text = str(expr or "").strip()
    if not text:
        _warn_once(f"[Eval] [{context}] Empty expression received; returning False")
        return False

    identifiers = _extract_identifiers(text)
    missing_vars = sorted(v for v in identifiers if v not in namespace)
    if missing_vars:
        _warn_once(
            f"[Eval] [{context}] Missing variables in namespace for expression '{text}': {', '.join(missing_vars)}"
        )
        return False

    try:
        return bool(eval(text, {"__builtins__": {}}, namespace))
    except Exception as error:
        _warn_once(
            f"[Eval] [{context}] Expression failed '{text}' -> {error}"
        )
        return False
