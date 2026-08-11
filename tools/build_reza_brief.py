#!/usr/bin/env python3
"""
Rebuilds reza-brief.html by injecting the current Apps Script into the template.

The brief embeds the whole of google-sheets/Code.gs so whoever is building the
forms can copy it straight off the page without needing repo access. That means
the two can drift apart, so the brief is generated rather than hand-edited.

    python3 tools/build_reza_brief.py           # rebuild
    python3 tools/build_reza_brief.py --check   # verify it is up to date

Edit tools/reza-brief.template.html for wording changes, never the generated
reza-brief.html.
"""

import argparse
import html
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "google-sheets" / "Code.gs"
TEMPLATE = ROOT / "tools" / "reza-brief.template.html"
OUTPUT = ROOT / "reza-brief.html"
MARKER = "<!--CODE_GS-->"


def build():
    code = SCRIPT.read_text(encoding="utf-8")
    template = TEMPLATE.read_text(encoding="utf-8")
    if MARKER not in template:
        sys.exit(f"{TEMPLATE.name} is missing the {MARKER} marker")
    return template.replace(MARKER, html.escape(code)), code


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", action="store_true",
                   help="Exit non-zero if the brief is stale, without rewriting it.")
    args = p.parse_args()

    rendered, code = build()

    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != rendered:
            sys.exit("reza-brief.html is out of date — run tools/build_reza_brief.py")
        print(f"reza-brief.html is up to date ({len(code.splitlines())} lines embedded)")
        return

    OUTPUT.write_text(rendered, encoding="utf-8")
    print(f"embedded {len(code.splitlines())} lines of Apps Script")
    print(f"wrote {OUTPUT.name} ({len(rendered):,} bytes)")


if __name__ == "__main__":
    main()
