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

# Modules of clear space around each QR, baked into the PNG. The spec requires
# four; anything less and some symbols quietly stop scanning.
QUIET_ZONE = 4

# Printed size of the QR on a sticker, in millimetres. 25 rather than 20
# because the deployment URL is long: the symbol runs to 53 modules, and at
# 20mm each module is 0.38mm — under what a cheap phone camera manages in a
# dark bar. At 25mm it is 0.47mm.
STICKER_QR_MM = 25

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


def derive_template(rows):
    """Work out the URL pattern a previous run used, from the master list.

    Reprints happen months later, by which point nobody remembers the exact
    form address. Rather than make them find it again — and silently produce
    dead QR codes if they get it wrong — recover it from the last batch.
    """
    if not rows:
        return None
    last = rows[-1]
    code, url = last.get("card_code", ""), last.get("qr_url", "")
    if not code or code not in url:
        return None
    return url.replace(code, "{code}")


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
    """One PNG per card, named after its code.

    border=4 is not cosmetic. The QR spec mandates a four-module quiet zone,
    and at border=2 roughly one symbol in fifty became unreadable — valid, but
    refused by stricter decoders. That failure mode is vicious in print: most
    cards work, a scattered few never do, and there is no way to tell which
    from looking at them.
    """
    d = os.path.join(OUTPUT_DIR, "qr_images", f"level_{level:02d}_{batch_slug}")
    os.makedirs(d, exist_ok=True)
    for r in rows:
        qr = segno.make(r["qr_url"], error="q")
        qr.save(os.path.join(d, f"{r['card_code']}.png"), scale=10, border=QUIET_ZONE)
    return d


def write_sticker_sheet(rows, level, batch_slug, qr_dir):
    """A4 sheets of stickers, QR at true printed size, ready to cut and apply.

    Print onto adhesive A4 and cut along the guides. Also serves as the proof
    for checking a batch scans before it goes anywhere near a card.

    Every sticker carries its own rank. Once these are cut apart a loose
    sticker is otherwise unidentifiable, and a level 4 sticker on a level 5
    card produces a card that will be refused at the bar with nothing to
    explain why. The rank is the cheapest possible guard against that.
    """
    d = os.path.join(OUTPUT_DIR, "sticker_sheets")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"level_{level:02d}_{batch_slug}_stickers.pdf")

    page_w, page_h = A4
    cols, rows_per_page = 5, 6
    per_page = cols * rows_per_page
    qr_size = STICKER_QR_MM * mm

    cell_w, cell_h = 38 * mm, 40 * mm
    margin_x = (page_w - cols * cell_w) / 2
    top = page_h - 26 * mm

    c = canvas.Canvas(path, pagesize=A4)

    for i, r in enumerate(rows):
        if i % per_page == 0:
            if i:
                c.showPage()
            c.setFont("Helvetica-Bold", 13)
            c.drawString(margin_x, page_h - 17 * mm,
                         f"LVL {r['level']} STICKERS  ·  {r['batch']}")
            c.setFont("Helvetica", 8)
            c.drawRightString(page_w - margin_x, page_h - 17 * mm,
                              f"page {i // per_page + 1}  ·  "
                              f"QR at {STICKER_QR_MM}mm actual size  ·  "
                              f"LVL {r['level']} cards only")

        slot = i % per_page
        col, row = slot % cols, slot // cols
        x = margin_x + col * cell_w
        y = top - (row + 1) * cell_h

        # Cut guide. Light enough not to matter if the scissors wander.
        c.setStrokeColorRGB(0.82, 0.82, 0.82)
        c.setLineWidth(0.25)
        c.rect(x, y, cell_w, cell_h)

        c.drawImage(os.path.join(qr_dir, f"{r['card_code']}.png"),
                    x + (cell_w - qr_size) / 2, y + 10 * mm,
                    width=qr_size, height=qr_size)
        c.setFont("Courier-Bold", 9)
        c.drawCentredString(x + cell_w / 2, y + 5.5 * mm, r["card_code"])
        c.setFont("Helvetica", 6)
        c.setFillColorRGB(0.45, 0.45, 0.45)
        c.drawCentredString(x + cell_w / 2, y + 2 * mm, f"LVL {r['level']}")
        c.setFillColorRGB(0, 0, 0)

    c.save()
    return path


# ---------------------------------------------------------------------------

def verify_images(rows):
    """Read back every QR that was just written and check it says what it should.

    Worth the few seconds. A QR can be generated perfectly and still be
    unreadable — too small a quiet zone did exactly that here, and the damage
    only shows up once cards are in people's hands. Generating and verifying
    are genuinely different operations, so this does not trust the writer.
    """
    try:
        import cv2
    except ImportError:
        print("\n(Skipping scan check — install opencv-python-headless to enable it.)")
        return 0

    detector = cv2.QRCodeDetector()
    unreadable, wrong = [], []

    for r in rows:
        path = os.path.join(OUTPUT_DIR, "qr_images",
                            f"level_{int(r['level']):02d}_"
                            f"{r['batch'].rsplit(' L', 1)[0].replace(' ', '-').replace('/', '-')}",
                            f"{r['card_code']}.png")
        if not os.path.exists(path):
            unreadable.append(r["card_code"])
            continue
        data, _, _ = detector.detectAndDecode(cv2.imread(path))
        if not data:
            unreadable.append(r["card_code"])
        elif data != r["qr_url"]:
            wrong.append(r["card_code"])

    if wrong:
        print("\n" + "!" * 70, file=sys.stderr)
        print("SCAN CHECK FAILED — do not print.", file=sys.stderr)
        print(f"  {len(wrong)} image(s) decoded to the wrong address: "
              f"{', '.join(wrong[:6])}", file=sys.stderr)
        print("!" * 70, file=sys.stderr)
        return None

    if not unreadable:
        print(f"\nScan check: all {len(rows)} QR images read back correctly.")
    return unreadable


def previously_held():
    """Codes held back by an earlier run.

    A hold has to be permanent. Once a code is dropped from a print run it gets
    voided in the spreadsheet, so letting a later run resurrect it — because a
    shorter URL happened to make its symbol easier to read — would put a card
    in the stack that the database refuses. Held stays held.
    """
    path = os.path.join(OUTPUT_DIR, "do_not_print.csv")
    if not os.path.exists(path):
        return set()
    with open(path, newline="", encoding="utf-8") as f:
        return {r["card_code"] for r in csv.DictReader(f)}


def quarantine(rows, bad_codes):
    """Drop codes the scan check could not read from everything printable.

    Some symbols are valid but sit awkwardly for a given decoder. Rather than
    argue about whether a particular phone would cope, they are simply never
    printed — codes are free and cards are not. The rows stay in the master
    list so the code can never be reissued, and are listed for voiding in the
    spreadsheet so nobody wonders where they went.
    """
    bad = set(bad_codes)
    keep = [r for r in rows if r["card_code"] not in bad]

    path = os.path.join(OUTPUT_DIR, "do_not_print.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["card_code", "level", "reason"])
        w.writeheader()
        for r in rows:
            if r["card_code"] in bad:
                w.writerow({"card_code": r["card_code"], "level": r["level"],
                            "reason": "held back — failed a scan check"})

    groups = {}
    for r in keep:
        level = int(r["level"])
        label = r["batch"].rsplit(f" L{level}", 1)[0]
        groups.setdefault((level, label), []).append(r)

    for (level, label), group in groups.items():
        slug = label.replace(" ", "-").replace("/", "-")
        write_printer_csv(group, level, slug)
        write_designer_csv(group, level, slug)
        # The sticker sheets are the product now, not just a proof — a held-back
        # code left on one would get stuck to a real card.
        qr_dir = os.path.join(OUTPUT_DIR, "qr_images", f"level_{level:02d}_{slug}")
        if os.path.isdir(qr_dir):
            write_sticker_sheet(group, level, slug, qr_dir)

    # The spreadsheet import, if one exists, should describe reality too: a
    # held-back code is void, not waiting to be issued. Anyone rebuilding the
    # sheet from these files then gets the right state without being told.
    import_dir = os.path.join(OUTPUT_DIR, "for_airtable")
    if os.path.isdir(import_dir):
        for name in os.listdir(import_dir):
            if not name.endswith(".csv"):
                continue
            ipath = os.path.join(import_dir, name)
            with open(ipath, newline="", encoding="utf-8") as f:
                irows = list(csv.DictReader(f))
            for r in irows:
                if r["card_code"] in bad:
                    r["status"] = "void"
            with open(ipath, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["card_code", "level", "status", "batch"])
                w.writeheader()
                w.writerows(irows)

    print(f"\n{len(bad)} code(s) held back from printing: {', '.join(sorted(bad))}")
    print("Printer, designer and sticker files rewritten without them.")
    print("Spreadsheet import marks them 'void'.")
    print(f"Listed in {path} — set these two rows to 'void' in the Cards tab.")
    return 0


def retarget(rows, url_template):
    """Point every existing code at a new address and redraw its QR.

    Used once the real form exists. Codes are deliberately left alone: by this
    point they are already sitting in the Cards tab of the spreadsheet, and
    generating fresh ones would silently invalidate every row there. Only the
    URL each code is wrapped in changes, so nothing downstream breaks.
    """
    if not rows:
        print("Nothing to retarget — no codes have been generated yet.", file=sys.stderr)
        return 1

    for r in rows:
        r["qr_url"] = url_template.format(code=r["card_code"])

    # Rows carry a batch label like "2026-08-launch L3"; recover the batch name
    # so the rewritten files land on top of the originals rather than beside them.
    groups = {}
    for r in rows:
        level = int(r["level"])
        label = r["batch"]
        suffix = f" L{level}"
        if label.endswith(suffix):
            label = label[: -len(suffix)]
        groups.setdefault((level, label), []).append(r)

    for (level, label) in sorted(groups):
        group = groups[(level, label)]
        slug = label.replace(" ", "-").replace("/", "-")
        write_printer_csv(group, level, slug)
        write_designer_csv(group, level, slug)
        qr_dir = write_qr_images(group, level, slug)
        write_sticker_sheet(group, level, slug, qr_dir)
        print(f"Level {level:>2}  {len(group):>4} cards redrawn   ({label})")

    write_master(MASTER_CSV, rows)

    bad = verify_images(rows)
    if bad is None:
        return 1
    bad = set(bad) | previously_held()
    if bad:
        quarantine(rows, bad)

    print(f"\nRe-aimed {len(rows)} existing codes. No new codes were created.")
    print(f"QR codes now point at {url_template.replace('{code}', 'XXXXXX')}")
    print("\nThe spreadsheet needs no changes — the codes in the Cards tab are")
    print("unchanged and still correct. Only the printed QR images differ.")
    print("\nScan one image from output/qr_images/ before sending anything to")
    print("a printer. It should open the form with the code already filled in.")
    return 0


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
    p.add_argument("--retarget", action="store_true",
                   help="Re-aim every EXISTING code at a new address and redraw "
                        "its QR. Creates no new codes — use this once the real "
                        "form exists, so the spreadsheet stays valid.")
    args = p.parse_args()

    if args.level and not args.count:
        p.error("--level needs --count as well")
    if args.base_url and args.url_template:
        p.error("use --base-url or --url-template, not both")
    if args.retarget:
        if not (args.base_url or args.url_template):
            p.error("--retarget needs the new address: --base-url or --url-template")
        if args.level or args.count:
            p.error("--retarget covers every existing code; drop --level and --count")

    batch_slug = args.batch.replace(" ", "-").replace("/", "-")

    existing_rows, taken = load_existing(MASTER_CSV)
    if existing_rows:
        print(f"Found {len(existing_rows)} existing codes — new ones will avoid them.")

    if args.url_template:
        url_template = args.url_template
        if "{code}" not in url_template:
            p.error("--url-template must contain {code} so each card differs")
        source = "the address you passed in"
    elif args.base_url:
        url_template = args.base_url.rstrip("/") + "?c={code}"
        source = "the address you passed in"
    else:
        # No address given: reuse whatever the last batch pointed at, so a
        # reprint cannot quietly end up aimed somewhere else.
        inherited = derive_template(existing_rows)
        url_template = inherited or DEFAULT_URL_TEMPLATE
        source = "the previous batch" if inherited else "the built-in placeholder"

    print(f"QR codes will point at {url_template.replace('{code}', 'XXXXXX')}")
    print(f"  (taken from {source})\n")

    if args.retarget:
        return retarget(existing_rows, url_template)

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
        stickers = write_sticker_sheet(rows, level, batch_slug, qr_dir)
        print(f"Level {level:>2}  {count:>4} cards   {printer_csv}")
        print(f"{'':13}{'':>4}          {designer_csv}")
        print(f"{'':13}{'':>4}          {stickers}")

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

    bad = verify_images(all_new)
    if bad is None:
        return 1
    bad = set(bad) | previously_held()
    if bad:
        quarantine(all_new, bad)

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
