# V3 Universes

These files are for the future V3 `/stocktips` pipeline only.

Supported formats:

- `.txt`
- `.json`
- `.csv`

## Built-in names

The V3 universe loader currently recognizes:

- `watchlist`
- `custom`
- `nifty200`
- `nifty500`
- `metals`
- `banks`

## Text format

One symbol per line:

```text
RELIANCE
TCS
HDFCBANK
```

The loader normalizes plain NSE symbols automatically to `.NS`.

## CSV format

Include one of these headers:

- `symbol`
- `ticker`
- `stock`
- `code`

## JSON format

Either:

```json
["RELIANCE", "TCS", "HDFCBANK"]
```

or:

```json
{"symbols": ["RELIANCE", "TCS", "HDFCBANK"]}
```

## Current note

These files are not yet wired into the current bot commands.
They are a separate foundation for V3 universe scanning.
