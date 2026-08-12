#!/usr/bin/env python3
"""
Rebuilds ray-brief.html by injecting the web app starter files.

The brief embeds Webapp.gs and Index.html in full so they can be copied
straight off the page without repo access. Generated rather than hand-edited,
so the page and the files cannot drift apart.

    python3 tools/build_ray_brief.py           # rebuild
    python3 tools/build_ray_brief.py --check   # verify it is up to date

Edit tools/ray-brief.template.html for wording, never the generated file.
"""

import argparse
import html
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "tools" / "ray-brief.template.html"
OUTPUT = ROOT / "ray-brief.html"

SOURCES = {
    "<!--CODE_GS-->": ROOT / "google-sheets" / "Code.gs",
    "<!--WEBAPP_GS-->": ROOT / "google-sheets" / "webapp" / "Webapp.gs",
    "<!--INDEX_HTML-->": ROOT / "google-sheets" / "webapp" / "Index.html",
}


def build():
    rendered = TEMPLATE.read_text(encoding="utf-8")
    counts = {}
    for marker, path in SOURCES.items():
        if marker not in rendered:
            sys.exit(f"{TEMPLATE.name} is missing the {marker} marker")
        text = path.read_text(encoding="utf-8")
        counts[path.name] = len(text.splitlines())
        rendered = rendered.replace(marker, html.escape(text))
    return rendered, counts


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", action="store_true",
                   help="Exit non-zero if the brief is stale, without rewriting it.")
    args = p.parse_args()

    rendered, counts = build()

    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != rendered:
            sys.exit("ray-brief.html is out of date — run tools/build_ray_brief.py")
        print(f"ray-brief.html is up to date ({', '.join(f'{k}: {v} lines' for k, v in counts.items())})")
        return

    OUTPUT.write_text(rendered, encoding="utf-8")
    for name, lines in counts.items():
        print(f"embedded {name} ({lines} lines)")
    print(f"wrote {OUTPUT.name} ({len(rendered):,} bytes)")


if __name__ == "__main__":
    main()
