---
name: refresh-logbook
description: Sync a board database and re-export the logbook CSV that analysis.ipynb reads.
disable-model-invocation: true
---

Pull down fresh climbing data and leave `analysis.ipynb` ready to run.

This costs real network traffic and a real login to the board, so the aim is to run each step once, deliberately, and notice when one goes wrong rather than pressing on.

## Arguments

`$ARGUMENTS` is `<board> <username>`, both optional.

Work out what is missing before running anything:

- **Board** — if a `<board>.sqlite3` already sits in the repo root, that is almost certainly the board wanted; use it. Otherwise ask.
- **Username** — the board account name, not a local username, and there is nowhere to look it up. Ask if it was not given.

Guessing either one wastes a slow download or burns a failed login attempt, which is why it is worth resolving up front.

## 1. Use the venv without activating it

Call the binaries by path:

```
.venv/bin/boardlib ...
.venv/bin/python ...
```

`source .venv/bin/activate` looks tempting but does not survive between commands — each one runs in its own shell, so the activation is lost and the next call silently falls back to system Python. Calling by path sidesteps that entirely.

If `.venv` is missing, create it once:

```
python3 -m venv .venv && .venv/bin/pip install -e ".[analysis]"
```

The `[analysis]` extra brings in the plotting stack the notebook needs, so installing it now avoids a second round trip later.

## 2. Confirm the password is exported

The CLI reads `{BOARD}_PASSWORD` — uppercase board name, e.g. `KILTER_PASSWORD`.

Check it is set before going near the network. If it is not, ask the user to export it and stop there. This matters more than it looks: with no env var the CLI falls back to an interactive `getpass` prompt, which has no terminal to read from here and will simply hang until the call times out.

## 3. Sync the board database

```
.venv/bin/boardlib database <board> <board>.sqlite3 -u <username>
```

First run downloads the board's SQLite out of an Android APK on apkpure — several MB, slow, and chatty on stdout. If the file already exists only the sync runs, which is much quicker.

Moonboard has no database at all; the `database` subcommand does not even accept a `moon*` board name. For those, skip straight to step 4 and leave off `-d`.

## 4. Export the logbook

If an `output` file is already there, note its line count first:

```
wc -l output
```

That count includes the header row, so it is one more than the number of ascents.

Then export:

```
.venv/bin/boardlib logbook <board> -u <username> -o output -d <board>.sqlite3
```

`output` is a literal filename, not a placeholder — `analysis.ipynb` reads exactly that path from the repo root, so renaming it breaks the notebook.

Knowing the old line count is what makes a half-finished export visible. The command writes the file as it goes, so an interrupted run leaves a short CSV that looks perfectly valid on its own.

## 5. Summarise what landed

Compute the summary rather than reading the CSV into context — it grows with every ascent logged, and the interesting facts are a few aggregates:

```
.venv/bin/python -c "
import pandas as pd
df = pd.read_csv('output')
print('rows      ', len(df))
print('dates     ', df['date'].min(), '->', df['date'].max())
print('angles    ', sorted(int(a) for a in df['angle'].dropna().unique()))
print('ascents   ', int(df['is_ascent'].sum()))
"
```

Report those figures, and say plainly whether the row count moved versus step 4. A count that dropped, or a date range that stops well short of today, is the signal that the sync did not finish — worth flagging rather than declaring success.

## When something fails

Say which step broke and what the board actually returned. Two failures are common and mean different things:

- **422 on login** — wrong username or password, so re-running changes nothing until the credentials are fixed.
- **Anything mid-sync** — the codebase has no retry or rate-limit handling anywhere, so a transient network error just surfaces. Re-running the same command is the fix, and the existing `.sqlite3` means it resumes rather than starting the download again.
