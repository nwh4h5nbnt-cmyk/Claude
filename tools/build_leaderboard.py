#!/usr/bin/env python3
"""
Builds leaderboard.html — the cumulative standings page for a GeoGuessr tournament.

Party mode wipes its leaderboard every time the host changes map, so the running
total has to live outside the game. geoguessr/tournament.json is that record:
one entry per map, holding the end-of-map scores exactly as they appeared. This
script adds a map to it and regenerates the page.

    python3 tools/build_leaderboard.py                      # rebuild the page
    python3 tools/build_leaderboard.py --check              # is the page stale?
    python3 tools/build_leaderboard.py add \
        --map "A Community World" --file round2.txt         # add a map, rebuild

The --file for `add` is the map's final leaderboard, one player per line, pasted
or typed off the screenshot:

    1. Open World      2,377 points
    2. Hahahehe        1,395 points

Leading places, thousands separators and a trailing "points" are all optional —
the last number on the line is the score and everything before it is the name.
Do not include the rating badge that sits next to a player's name; it is another
number and the parser cannot tell it from a score.

Renames are handled by "aliases" in the JSON: {"NewHandle": "OldHandle"} folds a
player's new name back onto the one already on the board. `add` flags names it
has not seen before that look like near misses of an existing player.

Edit tools/leaderboard.template.html for wording or layout, never the generated
leaderboard.html.
"""

import argparse
import datetime as dt
import difflib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "geoguessr" / "tournament.json"
TEMPLATE = ROOT / "tools" / "leaderboard.template.html"
OUTPUT = ROOT / "leaderboard.html"
MARKER = "/*__DATA__*/"

# "1." or "1)" at the head of a line — the place, which we recompute ourselves.
PLACE = re.compile(r"^\s*\d{1,3}\s*[.)]\s*")
# A trailing score: digits with optional , . or space separators, then "points".
SCORE = re.compile(r"([0-9][0-9,.  ]*)\s*(?:pts?|points?)?\s*$", re.I)


def load(path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def canonical(name, aliases):
    """Fold a player's later handle back onto the name already on the board."""
    seen = set()
    while name in aliases and name not in seen:
        seen.add(name)
        name = aliases[name]
    return name


def parse_scores(text, aliases):
    """Read a pasted map leaderboard into {player: score}."""
    scores, problems = {}, []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        line = PLACE.sub("", line)
        m = SCORE.search(line)
        if not m:
            problems.append(f"line {lineno}: no score found in {raw.strip()!r}")
            continue

        digits = re.sub(r"[^0-9]", "", m.group(1))
        name = line[: m.start()].strip(" \t:, -")
        if not digits or not name:
            problems.append(f"line {lineno}: could not split name from score in {raw.strip()!r}")
            continue

        name = canonical(name, aliases)
        if name in scores:
            problems.append(f"line {lineno}: {name!r} appears twice")
            continue
        scores[name] = int(digits)

    return scores, problems


def warn_near_misses(new_names, known):
    """A renamed player would otherwise silently start a second running total."""
    for name in sorted(set(new_names) - known):
        close = difflib.get_close_matches(name, sorted(known), n=1, cutoff=0.75)
        if close:
            print(
                f"  ! {name!r} is new but looks like {close[0]!r}. If they renamed, add\n"
                f'      "{name}": "{close[0]}"\n'
                f"    to \"aliases\" in {DATA.name} and re-run.",
                file=sys.stderr,
            )
        else:
            print(f"  + {name} joins the board")


def add_map(args):
    data = load(DATA)
    aliases = data.get("aliases", {})
    text = pathlib.Path(args.file).read_text(encoding="utf-8")

    scores, problems = parse_scores(text, aliases)
    for p in problems:
        print(f"  ! {p}", file=sys.stderr)
    if not scores:
        sys.exit("no scores parsed — nothing added")

    over = {p: s for p, s in scores.items() if s > args.max}
    if over:
        listed = ", ".join(f"{p} {s:,}" for p, s in over.items())
        sys.exit(f"score above the {args.max:,} maximum: {listed}\n"
                 f"pass --max if this map had a different round count")

    if data.get("sample"):
        print(f"clearing {len(data['maps'])} sample maps — this is the first real one")
        data["maps"] = []
        data["sample"] = False

    known = {p for m in data["maps"] for p in m["scores"]}
    if known:
        warn_near_misses(scores, known)
        missing = sorted(known - set(scores))
        if missing:
            print(f"  · not on this map (counts as 0): {', '.join(missing)}")

    data["maps"].append({
        "n": len(data["maps"]) + 1,
        "name": args.map,
        "mode": args.mode,
        "max": args.max,
        "played": args.date or dt.date.today().isoformat(),
        "scores": scores,
    })
    data["updated"] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

    DATA.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"map {len(data['maps'])}: {args.map} — {len(scores)} players")
    return data


def render(data):
    template = TEMPLATE.read_text(encoding="utf-8")
    if MARKER not in template:
        sys.exit(f"{TEMPLATE.name} is missing the {MARKER} marker")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    # The payload sits inside a <script>; only "</" can end it early.
    payload = payload.replace("</", "<\\/")
    return template.replace(MARKER, payload, 1)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--check", action="store_true",
                   help="Exit non-zero if leaderboard.html is stale, without rewriting it.")
    sub = p.add_subparsers(dest="cmd")

    a = sub.add_parser("add", help="Add one map's results and rebuild.")
    a.add_argument("--map", required=True, help='Map name, e.g. "A Community World".')
    a.add_argument("--file", required=True, help="File holding the map's final leaderboard.")
    a.add_argument("--mode", default="", help='Game settings, e.g. "Moving · 5 rounds".')
    a.add_argument("--max", type=int, default=25000,
                   help="Highest score this map could award (default 25000 = 5 rounds).")
    a.add_argument("--date", default="", help="Date played, YYYY-MM-DD (default today).")

    args = p.parse_args()

    data = add_map(args) if args.cmd == "add" else load(DATA)
    rendered = render(data)

    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != rendered:
            sys.exit("leaderboard.html is out of date — run tools/build_leaderboard.py")
        print(f"leaderboard.html is up to date ({len(data['maps'])} maps)")
        return

    OUTPUT.write_text(rendered, encoding="utf-8")
    players = len({p for m in data["maps"] for p in m["scores"]})
    print(f"wrote {OUTPUT.name} ({len(rendered):,} bytes) "
          f"— {len(data['maps'])} maps, {players} players")


if __name__ == "__main__":
    main()
