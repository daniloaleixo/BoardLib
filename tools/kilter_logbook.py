"""Export a Kilter logbook from the post-Aurora stack into BoardLib's CSV format.

Kilter left Aurora in March 2026, so `boardlib logbook kilter` can no longer
work -- kilterboardapp.com is decommissioned. The new app keeps ascents in a
PowerSync table called `logs`, which carries climb_uuid but no climb names or
grades. Those still come from the Aurora-era SQLite: Kilter kept the climb
UUIDs across the split, and the 39-entry difficulty scale is unchanged, so the
old database remains a valid lookup table even though its API is gone.

Output matches boardlib's LOGBOOK_FIELDS exactly, so analysis.ipynb is unaffected.
"""
import argparse
import os
import sqlite3
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kilter_sync import login, stream

FIELDS = (
    "board", "angle", "climb_name", "date", "logged_grade", "displayed_grade",
    "is_benchmark", "tries", "is_mirror", "sessions_count", "tries_total",
    "is_repeat", "is_ascent", "comment",
)


def rows(tables, name):
    return [r["row"] for r in tables.get(name, []) if isinstance(r.get("row"), dict)]


def to_grade(mapping, difficulty):
    if difficulty is None:
        return None
    try:
        return mapping.get(round(float(difficulty)))
    except (TypeError, ValueError):
        return None


def build(tables, db_path, board="kilter"):
    con = sqlite3.connect(db_path)
    grades = dict(con.execute("select difficulty, boulder_name from difficulty_grades"))
    names = dict(con.execute("select uuid, name from climbs"))
    stats = {
        (u, float(a)): (d, b)
        for u, a, d, b in con.execute(
            "select climb_uuid, angle, display_difficulty, benchmark_difficulty"
            " from climb_stats"
        )
    }

    # The user's own logged grade lives in climb_ratings, keyed by climb+angle.
    ratings = {}
    for r in rows(tables, "climb_ratings"):
        ratings[(r["climb_uuid"], float(r["angle"]))] = r

    entries, unknown = [], 0
    for log in rows(tables, "logs"):
        uuid, angle = log["climb_uuid"], float(log["angle"])
        name = names.get(uuid)
        if name is None:
            unknown += 1
            name = f"(unknown climb {uuid[:8]})"
        display, benchmark = stats.get((uuid, angle), (None, None))
        rating = ratings.get((uuid, angle))
        entries.append({
            "board": board,
            "angle": int(angle),
            "climb_name": name,
            "date": log["created_at"],
            "logged_grade": to_grade(grades, rating["difficulty_grade_id"]) if rating else None,
            "displayed_grade": to_grade(grades, display),
            "is_benchmark": bool(benchmark),
            "tries": int(log["attempts"] or 0),
            # The new logs table has no mirror flag; Aurora's did.
            "is_mirror": False,
            "is_ascent": str(log["topped"]) == "1",
            "comment": (rating or {}).get("comment"),
        })

    df = pd.DataFrame(entries)
    if df.empty:
        return df, unknown
    df["date"] = pd.to_datetime(df["date"], format="mixed", utc=True).dt.tz_localize(None)

    # Same derivations boardlib applies, so the columns keep their meaning.
    group = ["climb_name", "is_mirror", "angle"]
    df = df.sort_values("date").reset_index(drop=True)
    df["sessions_count"] = (
        df.groupby(group)["date"].transform(lambda s: s.dt.date.rank(method="dense").astype(int))
    )
    df["tries_total"] = df.groupby(group)["tries"].cumsum()
    df["is_repeat"] = df.duplicated(subset=group, keep="first")
    return df[list(FIELDS)].sort_values("date"), unknown


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("-d", "--database", default="kilter.sqlite3")
    p.add_argument("-o", "--output", default="output")
    args = p.parse_args()

    user, pw = os.environ.get("KILTER_USERNAME"), os.environ.get("KILTER_PASSWORD")
    if not user or not pw:
        raise SystemExit("set KILTER_USERNAME and KILTER_PASSWORD")
    if not os.path.exists(args.database):
        raise SystemExit(f"missing {args.database} (Aurora-era catalogue, needed for names/grades)")

    df, unknown = build(stream(login(user, pw)), args.database)
    if df.empty:
        raise SystemExit("no logs returned")
    df.to_csv(args.output, index=False)
    print(f"wrote {args.output}: {len(df)} rows")
    if unknown:
        print(f"note: {unknown} log(s) reference climbs absent from the Aurora catalogue")


if __name__ == "__main__":
    main()
