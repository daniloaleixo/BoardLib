# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## This fork

Personal fork of `lemeryfertitta/BoardLib`, used to pull climbing logbook data and explore it in `analysis.ipynb`. Changes are not expected to go upstream. There is no `upstream` remote configured.

`analysis.ipynb` reads a CSV named literally `output` from the repo root — produced by the `logbook` command. It also imports `matplotlib`, `seaborn`, and `numpy`, none of which are declared in `pyproject.toml` or `requirements.txt`; install them separately.

## Setup

The `src/` layout means nothing importable works until the package is installed:

```
python3 -m venv .venv && source .venv/bin/activate && pip install -e .
```

## Tests

Run from the repo root (the suites import `tests.boardlib.api.requests_mocks` by full path):

```
python -m unittest discover
```

**`tests/boardlib/api/test_aurora.py` is stale and fails.** It patches `get_climb_stats`, `user_sync`, and `get_climb_name` — none of which exist in `src/boardlib/api/aurora.py` anymore (`get_climb_name` moved to `boardlib.db.aurora`, `user_sync` became `sync`). Treat those 6 errors as pre-existing, not as something a change broke.

`test_moon.py` runs (14 tests) but `test_logbook_entries` also fails pre-existing: `moon.py:164` reads `entry["Problem"]["Grade"]` and the mock fixture has no `Grade` key. Baseline is 1 error there.

All tests mock `requests`; none touch the network. Nothing runs tests or lint in CI — the only workflow publishes to PyPI on release.

## Lint

`ruff check .`, configured in `pyproject.toml`. The rule set is pinned explicitly rather than inheriting ruff's implicit defaults, which span 400+ rules and shift between releases. `analysis.ipynb` is excluded. `E501` is off on purpose: 28 existing lines exceed 88 chars, and reflowing them would bury real changes in formatting noise. Do not run `ruff format` across the repo for the same reason.

## Python version

`requires-python = ">=3.8"` in `pyproject.toml` is wrong. The code uses `list[str]` annotations (`api/aurora.py`), `dict.keys() | dict.keys()` set ops, and `sys.stdout.reconfigure` (`__main__.py`), so it needs 3.9+ in practice. Write modern syntax; do not rewrite existing code for 3.8.

## Credentials

Board passwords come from a `{BOARD}_PASSWORD` env var — `KILTER_PASSWORD`, `TENSION_PASSWORD`, `MOON2019_PASSWORD` (`__main__.py:get_password`). There is no password CLI flag; the fallback is an interactive `getpass` prompt.

## Adding a board

Aurora-family boards (kilter, tension, decoy, grasshopper, soill, touchstone, aurora) are registered in two parallel dicts — `HOST_BASES` in `src/boardlib/api/aurora.py` and `APP_PACKAGE_NAMES` in `src/boardlib/db/aurora.py`. Adding an entry to both is enough; argparse derives its `choices` from `HOST_BASES`. Moonboard variants live in `BOARD_IDS` and `ANGLES_TO_IDS` in `src/boardlib/api/moon.py`.

A genuinely new provider needs more: board-family dispatch is a hardcoded `board.startswith("moon")` check in `__main__.py`.

## Network behaviour to preserve

- `db/aurora.py:download_database` scrapes the board SQLite out of the Android APK on apkpure, unzipping an XAPK then the inner APK. The browser `User-Agent` header is required — apkpure returns 403 without it. Aurora API calls separately spoof an iOS `User-Agent`.
- `api/aurora.py:sync` builds its form body by hand-encoding, because the endpoint rejects standard form encoding. Leave that encoding alone.
- Auth is a session token from `POST /sessions` passed as a raw `Cookie: token=...` header on every subsequent call.
- No retries or rate-limit handling exist anywhere; every response goes through `raise_for_status()`.

## Command order

For Aurora boards, `database` must run before `logbook` or `images` — the logbook joins against the local SQLite for climb names and grades. Moonboard is logbook-only and needs no database.

## Commits

Short imperative sentence-case subjects ("Fix moonboard logbook", "Skip existing files in image download"). Not Conventional Commits.
