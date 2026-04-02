"""
universe_loader.py — V3 universe loading helpers for /stocktips.

This module is intentionally separate from the current watchlist/report flow.
It loads stock universes from:

- built-in named universes
- text files
- JSON files
- CSV files
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from config import SYMBOL_ALIASES, WATCHLIST


V3_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = V3_DIR.parent
UNIVERSE_DIR = PROJECT_ROOT / "data" / "universes"


BUILTIN_UNIVERSES = {
    "watchlist": list(WATCHLIST),
    "custom": UNIVERSE_DIR / "custom.txt",
    "custom1": UNIVERSE_DIR / "custom1.txt",
    "nifty200": UNIVERSE_DIR / "nifty200.txt",
    "nifty500": UNIVERSE_DIR / "nifty500.txt",
    "metals": UNIVERSE_DIR / "metals.txt",
    "banks": UNIVERSE_DIR / "banks.txt",
}


def _normalize_symbol(symbol: str) -> str:
    raw = (symbol or "").strip().upper()
    if not raw:
        return ""

    if raw in SYMBOL_ALIASES:
        return SYMBOL_ALIASES[raw]

    if raw.endswith(".NS") or raw.endswith(".BO"):
        return raw

    return f"{raw}.NS"


def _dedupe_keep_order(symbols: list[str]) -> list[str]:
    seen = set()
    ordered = []
    for symbol in symbols:
        normalized = _normalize_symbol(symbol)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _load_text_universe(path: Path) -> list[str]:
    symbols = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        symbols.append(line.split(",")[0].strip())
    return _dedupe_keep_order(symbols)


def _load_json_universe(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        if isinstance(payload.get("symbols"), list):
            return _dedupe_keep_order([str(item) for item in payload["symbols"]])
        raise ValueError(f"JSON universe {path} must contain a 'symbols' list")
    if isinstance(payload, list):
        return _dedupe_keep_order([str(item) for item in payload])
    raise ValueError(f"JSON universe {path} must be a list or an object with 'symbols'")


def _load_csv_universe(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = [header.lower() for header in (reader.fieldnames or [])]
        if not headers:
            raise ValueError(f"CSV universe {path} has no header row")

        symbol_field = None
        for candidate in ("symbol", "ticker", "stock", "code"):
            if candidate in headers:
                symbol_field = candidate
                break

        if symbol_field is None:
            raise ValueError(
                f"CSV universe {path} must include one of: symbol, ticker, stock, code"
            )

        symbols = []
        for row in reader:
            for key, value in row.items():
                if key and key.lower() == symbol_field and value:
                    symbols.append(value.strip())
                    break
    return _dedupe_keep_order(symbols)


def load_universe_file(path: str | Path) -> list[str]:
    file_path = Path(path).expanduser().resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"Universe file not found: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix in {".txt", ".list"}:
        return _load_text_universe(file_path)
    if suffix == ".json":
        return _load_json_universe(file_path)
    if suffix == ".csv":
        return _load_csv_universe(file_path)

    raise ValueError(
        f"Unsupported universe file format for {file_path}. Use .txt, .json, or .csv"
    )


def resolve_universe_path(name: str) -> Path | None:
    value = BUILTIN_UNIVERSES.get((name or "").strip().lower())
    return value if isinstance(value, Path) else None


def load_universe(name_or_path: str = "watchlist") -> list[str]:
    """
    Load a V3 universe by built-in name or file path.

    Supported built-ins:
    - watchlist
    - custom
    - custom1
    - nifty200
    - nifty500
    - metals
    - banks
    """
    key = (name_or_path or "watchlist").strip().lower()

    if key == "watchlist":
        return _dedupe_keep_order(list(WATCHLIST))

    builtin_path = resolve_universe_path(key)
    if builtin_path is not None:
        return load_universe_file(builtin_path)

    return load_universe_file(name_or_path)


def universe_summary(name_or_path: str = "watchlist") -> dict:
    """
    Return a small metadata summary for UI/logging purposes.
    """
    symbols = load_universe(name_or_path)
    builtin_path = resolve_universe_path(name_or_path)

    if (name_or_path or "").strip().lower() == "watchlist":
        source = "builtin:watchlist"
    elif builtin_path is not None:
        source = str(builtin_path)
    else:
        source = str(Path(name_or_path).expanduser().resolve())

    return {
        "name": name_or_path,
        "count": len(symbols),
        "source": source,
        "symbols": symbols,
    }
