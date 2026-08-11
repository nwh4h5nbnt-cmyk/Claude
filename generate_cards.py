#!/usr/bin/env python3
"""
Loyalty card code generator.

Produces everything you need to send a print run to a printer, and everything
you need to import into Airtable so the database knows which codes are real.

You do not need to understand this file. Run it with:

    python3 generate_cards.py --base-url "https://your-domain.link/go"

Everything lands in output/. See README.md for what each file is for.

For a REPRINT: run it again with --level and --count. It reads the existing
master CSV first and guarantees the new codes never collide with old ones.
"""

import argparse
import csv
import os
import secrets
import sys
from datetime import date

import segno
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

# ---------------------------------------------------------------------------
# Settings you might want to change
# ---------------------------------------------------------------------------

# Ambiguous characters are deliberately excluded so nobody misreads a code
# written down by hand: no I, L, O, U, 0 or 1.
LETTERS = "ABCDEFGHJKMNPQRSTVWXYZ"
DIGITS = "23456789"
ALPHABET = LETTERS + DIGITS

CODE_LENGTH = 6

# How many cards to make per level, first run. These come out of
# estimate_print_run.py at its default assumptions: 250 signups over a
# six-month window, six stamps per card, one stamp per visit.
#
# The shape is driven as much by time as by drop-off — a rank takes weeks of
# visits to clear, so almost nobody reaches the top ranks inside the first
# window however keen they are. Re-run the estimator with your own numbers if
# they turn out different.
#
# Generating codes is free; only printing costs money. Generate all ten levels
# now and print the lower ones first.
DEFAULT_QUANTITIES = {
    1: 250,
    2: 125,
    3: 75,
    4: 50,
    5: 50,
    6: 25,
    7: 25,
    8: 25,
    9: 25,
    10: 25,
}

PLACEHOLDER_URL = "https://REPLACE-ME.link/go"

# Where the QR codes point. {code} is swapped for each card's code.
#
# If you have a short domain redirecting to your form, the simple version is
# best — a shorter URL means a less dense QR, which scans faster in dim light:
#     https://your-domain.link/go?c={code}
#
# If you are pointing straight at the Airtable form instead, use its prefill
# syntax so the code fills itself in and stays hidden from the member:
#     https://airtable.com/shrXXXXXXXX?prefill_Card+code={code}&hide_Card+code=true
DEFAULT_URL_TEMPLATE = PLACEHOLDER_URL + "?c={code}"

OUTPUT_DIR = "output"
MASTER_CSV = os.path.join(OUTPUT_DIR, "master_codes.csv")


# ---------------------------------------------------------------------------
# Code generation
# ---------------------------------------------------------------------------

def make_code():
    """One random code. Always starts with a letter so spreadsheets never
    mistake it for a number and mangle it into scientific notation."""
    first = secrets.choice(LETTERS)
    rest = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH - 1))
    return first + rest


def load_existing(path):
    """Every code ever generated, so a reprint can never reuse one."""
    if not os.path.exists(path):
        return [], set()
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return rows, {r["card_code"] for r in rows}


def generate_batch(count, taken):
    """`count` fresh codes, none of which already exist."""
    new = []
    while len(new) < count:
        code = make_code()
        if code in taken:
            continue
        taken.add(code)
        new.append(code)
    return new


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

def write_master(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["card_code", "level", "batch", "qr_url"])
        w.writeheader()
        w.writerows(rows)


def write_printer_csv(rows, level, batch_slug):
    """One CSV per level. The printer gets this plus that level's artwork."""
    d = os.path.join(OUTPUT_DIR, "for_printer")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"level_{level:02d}_{batch_slug}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["card_code", "level", "qr_url"])
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in ("card_code", "level", "qr_url")})
    return path


def write_designer_csv(rows, level, batch_slug):
    """A CSV shaped for InDesign's Data Merge panel.

    The @ prefix on a column header is how InDesign is told the values are
    image paths rather than text. Paths are relative to the CSV, so unzipping
    that level's QR archive alongside this file is all the setup needed.
    """
    d = os.path.join(OUTPUT_DIR, "for_designer")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"level_{level:02d}_{batch_slug}_indesign.csv")
    folder = f"level_{level:02d}_{batch_slug}"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["card_code", "@qr"])
        for r in rows:
            w.writerow([r["card_code"], os.path.join(folder, f"{r['card_code']}.png")])
    return path


def write_airtable_csv(rows, batch_slug):
    """Import straight into the Cards table. Every card starts unissued."""
    d = os.path.join(OUTPUT_DIR, "for_airtable")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"cards_import_{batch_slug}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["card_code", "level", "status", "batch"])
        w.writeheader()
        for r in rows:
            w.writerow({
                "card_code": r["card_code"],
                "level": r["level"],
                "status": "unissued",
                "batch": r["batch"],
            })
    return path


def write_qr_images(rows, level, batch_slug):
    """One PNG per card, named after its code."""
    d = os.path.join(OUTPUT_DIR, "qr_images", f"level_{level:02d}_{batch_slug}")
    os.makedirs(d, exist_ok=True)
    for r in rows:
        qr = segno.make(r["qr_url"], error="q")
        qr.save(os.path.join(d, f"{r['card_code']}.png"), scale=10, border=2)
    return d


def write_proof_pdf(rows, level, batch_slug, qr_dir):
    """A4 sheet of every QR at true printed size (20mm) with its code beneath.

    Two uses: check a batch scans correctly before accepting delivery, or
    print onto adhesive A4 and cut out as stickers if you go the sticker route
    instead of variable-data printing.
    """
    d = os.path.join(OUTPUT_DIR, "proof_sheets")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"level_{level:02d}_{batch_slug}_proof.pdf")

    page_w, page_h = A4
    cols, per_page = 4, 24
    margin_x, margin_y = 15 * mm, 20 * mm
    cell_w = (page_w - 2 * margin_x) / cols
    cell_h = 40 * mm
    qr_size = 20 * mm

    c = canvas.Canvas(path, pagesize=A4)

    for i, r in enumerate(rows):
        if i % per_page == 0:
            if i:
                c.showPage()
            c.setFont("Helvetica-Bold", 11)
            c.drawString(margin_x, page_h - margin_y + 6 * mm,
                         f"LEVEL {r['level']}  ·  batch {r['batch']}")
            c.setFont("Helvetica", 8)
            c.drawRightString(page_w - margin_x, page_h - margin_y + 6 * mm,
                              f"page {i // per_page + 1} · QR shown at 20mm actual size")

        slot = i % per_page
        col, row = slot % cols, slot // cols
        x = margin_x + col * cell_w
        y = page_h - margin_y - (row + 1) * cell_h

        c.drawImage(os.path.join(qr_dir, f"{r['card_code']}.png"),
                    x + (cell_w - qr_size) / 2, y + 12 * mm,
                    width=qr_size, height=qr_size)
        c.setFont("Courier-Bold", 10)
        c.drawCentredString(x + cell_w / 2, y + 6 * mm, r["card_code"])

    c.save()
    return path


# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Generate loyalty card codes and QR files.")
    p.add_argument("--base-url", default=None,
                   help="Shorthand for a simple link: QRs point at "
                        "BASE_URL?c=CODE. Use --url-template for anything else.")
    p.add_argument("--url-template", default=None,
                   help="Full URL pattern with {code} where the card code goes. "
                        "Needed when pointing straight at an Airtable form.")
    p.add_argument("--level", type=int,
                   help="Generate one level only (for reprints). Omit to do all ten.")
    p.add_argument("--count", type=int,
                   help="How many cards. Only used with --level.")
    p.add_argument("--batch", default=date.today().strftime("%Y-%m"),
                   help="Batch label, e.g. 2026-08 or 2026-11-reprint.")
    args = p.parse_args()

    if args.level and not args.count:
        p.error("--level needs --count as well")
    if args.base_url and args.url_template:
        p.error("use --base-url or --url-template, not both")

    if args.url_template:
        url_template = args.url_template
        if "{code}" not in url_template:
            p.error("--url-template must contain {code} so each card differs")
    elif args.base_url:
        url_template = args.base_url.rstrip("/") + "?c={code}"
    else:
        url_template = DEFAULT_URL_TEMPLATE

    batch_slug = args.batch.replace(" ", "-").replace("/", "-")

    existing_rows, taken = load_existing(MASTER_CSV)
    if existing_rows:
        print(f"Found {len(existing_rows)} existing codes — new ones will avoid them.\n")

    quantities = ({args.level: args.count} if args.level else DEFAULT_QUANTITIES)

    all_new = []
    for level in sorted(quantities):
        count = quantities[level]
        codes = generate_batch(count, taken)
        rows = [{
            "card_code": code,
            "level": level,
            "batch": f"{args.batch} L{level}",
            "qr_url": url_template.format(code=code),
        } for code in codes]
        all_new.extend(rows)

        printer_csv = write_printer_csv(rows, level, batch_slug)
        designer_csv = write_designer_csv(rows, level, batch_slug)
        qr_dir = write_qr_images(rows, level, batch_slug)
        proof = write_proof_pdf(rows, level, batch_slug, qr_dir)
        print(f"Level {level:>2}  {count:>4} cards   {printer_csv}")
        print(f"{'':13}{'':>4}          {designer_csv}")
        print(f"{'':13}{'':>4}          {proof}")

    write_master(MASTER_CSV, existing_rows + all_new)
    airtable_csv = write_airtable_csv(all_new, batch_slug)

    total = len(existing_rows) + len(all_new)
    print(f"\nGenerated {len(all_new)} new codes. Master now holds {total}.")
    print(f"Master list:      {MASTER_CSV}")
    print(f"Airtable import:  {airtable_csv}")

    # Sanity check. A duplicate code is the one failure this system cannot
    # recover from, so it is worth being loud about.
    all_codes = [r["card_code"] for r in existing_rows + all_new]
    if len(all_codes) != len(set(all_codes)):
        print("\nSTOP — duplicate codes detected. Do not print. Re-run.", file=sys.stderr)
        return 1

    if "REPLACE-ME" in url_template:
        print("\n" + "!" * 70)
        print("The QR images point at a placeholder domain and will NOT work.")
        print("Set up your form first, then re-run with the real address:")
        print('    python3 generate_cards.py --base-url "https://your-domain.link/go"')
        print("The codes themselves are fine — only the QR images depend on the")
        print("URL, so nothing is wasted by re-running.")
        print("!" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
