---
name: refresh-logbook
description: Sync a board database and export your logbook CSV, ready for analysis.ipynb.
disable-model-invocation: true
---

Refresh the local board database and re-export the logbook CSV that `analysis.ipynb` reads.

`$ARGUMENTS` is `<board> <username>`. If either is missing, ask before running anything — this hits the live network and consumes credentials.

## 1. Environment

Activate `.venv`. If it does not exist, create it and install the package editable:

```
python3 -m venv .venv && source .venv/bin/activate && pip install -e .
```

## 2. Password

Check whether `{BOARD}_PASSWORD` is set (uppercase board name, e.g. `KILTER_PASSWORD`). If it is not, tell the user to export it and stop — do not fall through to the interactive `getpass` prompt, which will hang.

## 3. Sync the database

```
boardlib database <board> <board>.sqlite3 -u <username>
```

This downloads the board SQLite out of the Android APK from apkpure on first run, then pages the sync API. It is slow and chatty. If the file already exists, only the sync runs.

Moonboard has no database command — for a `moon*` board, skip to step 4 and omit `-d`.

## 4. Export the logbook

```
boardlib logbook <board> -u <username> -o output -d <board>.sqlite3
```

The filename `output` is not a placeholder: `analysis.ipynb` reads exactly that path from the repo root.

## 5. Report

Read the CSV header and row count, and report: number of ascents, the date range covered, and the distinct angles present. Then confirm `analysis.ipynb` is ready to run.

If the export fails partway, say which step failed and what the board API returned. There are no retries in the codebase, so a transient failure means re-running the command.
