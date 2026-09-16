---
name: refresh-logbook
description: Sync a board database and re-export the logbook CSV that analysis.ipynb reads.
disable-model-invocation: true
---

Pull down fresh climbing data and leave `analysis.ipynb` ready to run.

This costs real network traffic and a real login, so the aim is to run each step once, deliberately, and notice when one goes wrong rather than pressing on.

Kilter and the other boards need different paths now — Kilter left Aurora in March 2026 and its old API is gone. Work out which board is in play before running anything.

## Arguments

`$ARGUMENTS` is `<board> <username>`, both optional.

- **Board** — if a `<board>.sqlite3` already sits in the repo root, that is almost certainly the board wanted; use it. Otherwise ask.
- **Username** — for Kilter this comes from `.env` (see step 2), so do not ask. For every other board it is the board account name, and there is nowhere to look it up, so ask if it was not given.

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

## 2. Credentials

Secrets live in `.env` in the repo root, which is gitignored. Never print the file or echo a value — pass it straight into the process that needs it:

```
KILTER_USERNAME="$(sed -n 's/^KILTER_USERNAME=//p' .env)"
KILTER_PASSWORD="$(sed -n 's/^KILTER_PASSWORD=//p' .env)"
```

Use that `sed` form rather than `source .env` or an `xargs` loop. Plain sourcing does not reliably export into child processes here, and the `xargs` idiom word-splits on spaces and strips quotes, which silently corrupts any password containing either. Command substitution passes the value through byte for byte.

If the value needed is missing, ask the user to add it and stop. Do not fall through to a prompt: `__main__.py:get_password` drops to an interactive `getpass` when its env var is unset, and with no terminal attached that hangs until the call times out.

A note on retrying logins: Keycloak returns the same `invalid_grant` / "Invalid user credentials" for a wrong username *and* a wrong password, so a failure tells you nothing about which half was wrong. Guessing also risks a brute-force lockout on the real account. Ask instead.

## 3. Get the data

Three paths. Pick by board.

### Kilter — the new stack

Aurora shut the Kilter backend down in March 2026. `kilterboardapp.com` now fails during the TLS handshake for everyone, so `boardlib logbook kilter` cannot work and there is no point retrying it. The new app authenticates via Keycloak and syncs over PowerSync; `tools/kilter_logbook.py` speaks both and writes the same CSV.

It still needs `kilter.sqlite3`, because the sync stream carries `climb_uuid` but no names or grades. Kilter kept the Aurora climb UUIDs across the split, so the old catalogue remains a valid lookup table. If the file is missing, download it **without** `-u`:

```
.venv/bin/boardlib database kilter kilter.sqlite3
```

Omitting `-u` is the important part — it downloads the APK-bundled database and skips the sync, and the sync is the half that would try to log into the dead host.

That database is effectively irreplaceable: it comes from the old Android app on apkpure, and when that download disappears there is no other source of Kilter climb names. Do not delete it.

Then export:

```
KILTER_USERNAME="$(sed -n 's/^KILTER_USERNAME=//p' .env)" \
KILTER_PASSWORD="$(sed -n 's/^KILTER_PASSWORD=//p' .env)" \
  .venv/bin/python tools/kilter_logbook.py -d kilter.sqlite3 -o output
```

Expect a line like `note: N log(s) reference climbs absent from the Aurora catalogue`. Those are climbs set *after* the split, which the frozen catalogue cannot name; they land as `(unknown climb <prefix>)`. A slowly growing N is normal, not a regression.

### Other Aurora boards — tension, aurora, decoy, grasshopper, soill, touchstone

These still work the way they always did, and their hosts were confirmed healthy after the split. The database must come first, because the logbook joins against it for names and grades:

```
.venv/bin/boardlib database <board> <board>.sqlite3 -u <username>
.venv/bin/boardlib logbook <board> -u <username> -o output -d <board>.sqlite3
```

First run downloads several MB out of an Android APK and is slow; later runs only sync.

### Moonboard

No database at all — the `database` subcommand does not accept a `moon*` name. Export directly, with no `-d`:

```
.venv/bin/boardlib logbook <board> -u <username> -o output
```

## 4. Know what you are overwriting

If an `output` file is already there, note its line count before exporting:

```
wc -l output
```

That count includes the header, so it is one more than the number of entries.

This matters because every path above writes `output` in place. An interrupted export leaves a short CSV that looks perfectly valid on its own — the previous count is the only thing that makes the truncation visible.

`output` is a literal filename, not a placeholder. `analysis.ipynb` reads exactly that path from the repo root, so renaming it breaks the notebook.

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

Report those figures and say plainly whether the row count moved versus step 4. A count that dropped, or a date range stopping well short of today, means the export did not finish — worth flagging rather than declaring success.

## When something fails

Say which step broke and what the server actually returned. The common failures mean different things:

- **`TLSV1_ALERT_INTERNAL_ERROR` on `kilterboardapp.com`** — the decommissioned Aurora host. Something used the old Kilter path; switch to `tools/kilter_logbook.py`. Retrying never helps.
- **HTTP 401 `invalid_grant` from `idp.kiltergrips.com`** — wrong Kilter credentials in `.env`. Re-running changes nothing until they are fixed, and repeated attempts risk a lockout.
- **422 on login to an Aurora board** — wrong username or password for that board, same reasoning.
- **Anything mid-sync** — there is no retry or rate-limit handling anywhere in the codebase, so a transient network error just surfaces. Re-running is the fix, and an existing `.sqlite3` means it resumes rather than re-downloading.
