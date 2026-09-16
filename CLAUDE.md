# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## This fork

Personal fork of `lemeryfertitta/BoardLib`, used to pull climbing logbook data and explore it in `analysis.ipynb`. Changes are not expected to go upstream. There is no `upstream` remote configured.

`analysis.ipynb` reads a CSV named literally `output` from the repo root — produced by the `logbook` command, or by `tools/kilter_logbook.py` for Kilter. Its extra imports (`matplotlib`, `numpy`, `seaborn`) are the `analysis` optional extra: `pip install -e ".[analysis]"`. They are deliberately kept out of `[project.dependencies]` so `pip install boardlib` does not pull plotting libraries.

## Setup

The `src/` layout means nothing importable works until the package is installed:

```
python3 -m venv .venv && source .venv/bin/activate && pip install -e .
```

Add the notebook's plotting stack with `pip install -e ".[analysis]"`.

## Tests

Run from the repo root (the suites import `tests.boardlib.api.requests_mocks` by full path):

```
python -m unittest discover
```

One known failure, pre-existing: `test_logbook_entries` in `test_moon.py`. `moon.py:164` reads `entry["Problem"]["Grade"]` and the mock fixture has no `Grade` key. Everything else passes — 25 tests, 1 error. Treat any other failure as something a change broke.

`sync` (`api/aurora.py`) and `get_climb_name` / `get_difficulty` (`db/aurora.py`) have no tests: the ones that covered them were written against renamed functions and were removed rather than rewritten.

All tests mock `requests`; none touch the network. Nothing runs tests or lint in CI — the only workflow publishes to PyPI on release.

## Lint

`ruff check .`, configured in `pyproject.toml`. The rule set is pinned explicitly rather than inheriting ruff's implicit defaults, which span 400+ rules and shift between releases. `analysis.ipynb` is excluded. `E501` is off on purpose: 28 existing lines exceed 88 chars, and reflowing them would bury real changes in formatting noise. Do not run `ruff format` across the repo for the same reason.

## Python version

`requires-python = ">=3.8"` in `pyproject.toml` is wrong. The code uses `list[str]` annotations (`api/aurora.py`), `dict.keys() | dict.keys()` set ops, and `sys.stdout.reconfigure` (`__main__.py`), so it needs 3.9+ in practice. Write modern syntax; do not rewrite existing code for 3.8.

## Credentials

Secrets live in `.env` in the repo root (gitignored). Read a value with `sed -n 's/^KEY=//p' .env` and pass it straight into the process — `source .env` does not reliably export into child processes here, and the `xargs` idiom word-splits on spaces and strips quotes.

`boardlib` itself reads a `{BOARD}_PASSWORD` env var — `TENSION_PASSWORD`, `MOON2019_PASSWORD` (`__main__.py:get_password`). There is no password CLI flag, and the fallback is an interactive `getpass` prompt that hangs when no terminal is attached.

Kilter is different: it needs `KILTER_USERNAME` (an email) as well as `KILTER_PASSWORD`, because the new stack authenticates against Keycloak rather than a board account name. Keycloak reports a wrong username and a wrong password identically, so failed logins are not worth guessing at — and repeats risk a lockout.

## Adding a board

Aurora-family boards (tension, decoy, grasshopper, soill, touchstone, aurora — no longer kilter, see below) are registered in two parallel dicts — `HOST_BASES` in `src/boardlib/api/aurora.py` and `APP_PACKAGE_NAMES` in `src/boardlib/db/aurora.py`. Adding an entry to both is enough; argparse derives its `choices` from `HOST_BASES`. Moonboard variants live in `BOARD_IDS` and `ANGLES_TO_IDS` in `src/boardlib/api/moon.py`.

A genuinely new provider needs more: board-family dispatch is a hardcoded `board.startswith("moon")` check in `__main__.py`.

## Kilter left Aurora (March 2026)

Aurora shut down the Kilter backend; `kilterboardapp.com` now fails during the TLS handshake for every client, from every network. `boardlib logbook kilter` therefore cannot work and is not fixable — retrying is pointless. The other Aurora boards were unaffected.

The new app uses Keycloak (`idp.kiltergrips.com`, realm `kilter`, public client `kilter`, password grant) and syncs rows over PowerSync (`POST sync1.kiltergrips.com/sync/stream`). `tools/kilter_sync.py` implements a read-only client for that stream; `tools/kilter_logbook.py` turns it into the standard `LOGBOOK_FIELDS` CSV. Run them via `/refresh-logbook`.

Ascents arrive in a `logs` table carrying `climb_uuid` but no names or grades. Those come from the Aurora-era `kilter.sqlite3`: Kilter kept the climb UUIDs across the split, and all 39 difficulty-grade IDs are unchanged, so the old catalogue is still a correct lookup table. Two consequences worth knowing:

- Climbs set *after* the split cannot be named, and export as `(unknown climb <prefix>)`. The count grows slowly; it is not a regression.
- `kilter.sqlite3` is effectively irreplaceable — it comes from the old Android app on apkpure, and nothing else publishes Kilter climb names. Do not delete it.

`logs` has no comment or mirror field, so `comment` is always empty and `is_mirror` is always `False` in Kilter exports.

## Network behaviour to preserve

- `db/aurora.py:download_database` scrapes the board SQLite out of the Android APK on apkpure, unzipping an XAPK then the inner APK. The browser `User-Agent` header is required — apkpure returns 403 without it. Aurora API calls separately spoof an iOS `User-Agent`.
- `api/aurora.py:sync` builds its form body by hand-encoding, because the endpoint rejects standard form encoding. Leave that encoding alone.
- Auth is a session token from `POST /sessions` passed as a raw `Cookie: token=...` header on every subsequent call.
- No retries or rate-limit handling exist anywhere; every response goes through `raise_for_status()`.

## Command order

For Aurora boards, `database` must run before `logbook` or `images` — the logbook joins against the local SQLite for climb names and grades. Moonboard is logbook-only and needs no database.

Kilter needs `kilter.sqlite3` too, but download it **without** `-u`: omitting the username skips the sync, and the sync is the half that would try to reach the dead Aurora host.

## Commits

Short imperative sentence-case subjects ("Fix moonboard logbook", "Skip existing files in image download"). Not Conventional Commits.
