#!/usr/bin/env python3
"""Build every HDR variant of the logo, then check each one really carries its tag.

Run it the same way on any machine, from the top of the repo:

    python3 brand/glow.py          # macOS / Linux
    python brand\\glow.py          # Windows

Or point it at artwork somewhere else:

    python3 brand/glow.py ~/Desktop/logo.png

Outputs land in brand/out/. Re-running overwrites them, so it is safe to run
again after you tweak the artwork.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

# Artwork we will pick up automatically if you don't name a file. PNG first
# because it is the one that keeps a transparent background.
CANDIDATES = ("logo.png", "logo.jpg", "logo.jpeg", "logo.webp")

# name -> nits. None means the JPEG path, which uses the ICC profile as-is.
BUILDS = (
    ("logo-hdr.jpg", None),
    ("logo-hdr-4000.png", 4000),
    ("logo-hdr-1000.png", 1000),
)

CONFLICTING = {b"iCCP", b"sRGB", b"gAMA", b"cHRM"}


def die(*lines):
    print("", file=sys.stderr)
    for line in lines:
        print(line, file=sys.stderr)
    sys.exit(1)


def find_source(argv):
    if len(argv) > 1:
        src = os.path.abspath(argv[1])
        if not os.path.isfile(src):
            die(f"There is no file at: {src}",
                "Check the path, or drop the artwork at brand/logo.png and run this",
                "again with no arguments.")
        return src

    for name in CANDIDATES:
        path = os.path.join(HERE, name)
        if os.path.isfile(path):
            return path

    die("I couldn't find the logo artwork.",
        "",
        f"Save it as brand/logo.png (that folder is: {HERE})",
        "and run this again. Square, at least 1000px, on black or transparent.",
        "",
        "Or point me straight at it:",
        f"    {os.path.basename(sys.executable) or 'python3'} brand/glow.py path/to/your-logo.png")


def check_pillow():
    try:
        import PIL  # noqa: F401
    except ImportError:
        py = sys.executable or "python3"
        die("This needs Pillow, which isn't installed.",
            "",
            "Install it with:",
            f'    "{py}" -m pip install pillow',
            "",
            "Then run this again.")


def png_chunk_types(path):
    data = open(path, "rb").read()
    i, types = 8, []
    while i < len(data):
        n = struct.unpack(">I", data[i:i + 4])[0]
        types.append(data[i + 4:i + 8])
        i += 12 + n
    return types


def verify(path, nits):
    """Confirm the HDR tag actually made it into the file we just wrote."""
    from PIL import Image

    if nits is None:
        ok = bool(Image.open(path).info.get("icc_profile"))
        return ok, "carries a Rec.2020+PQ ICC profile"

    types = png_chunk_types(path)
    ok = b"cICP" in types and not (CONFLICTING & set(types))
    return ok, "carries a clean cICP (BT.2020 + PQ) tag"


def main():
    check_pillow()
    src = find_source(sys.argv)

    # Imported after the Pillow check so a missing dependency gets the friendly
    # message above rather than a traceback.
    sys.path.insert(0, HERE)
    from hdr_glow import convert

    os.makedirs(OUT, exist_ok=True)
    print(f"Source: {src}")
    print("")

    results = []
    for name, nits in BUILDS:
        dst = os.path.join(OUT, name)
        convert(src, dst, nits if nits is not None else 1000)
        ok, what = verify(dst, nits)
        results.append(ok)
        print(f"  {'PASS' if ok else 'FAIL'}  {name} {what}")

    print("")
    if not all(results):
        die("Something went wrong — at least one file is missing its HDR tag.",
            "The files in brand/out/ should not be uploaded as they are.")

    print(f"Three files written to {OUT}")
    print("")
    print("  logo-hdr.jpg        -> upload this one to LinkedIn, as the *page* logo")
    print("  logo-hdr-4000.png   -> a page you host yourself, full burn")
    print("  logo-hdr-1000.png   -> same, turned down, safer next to body text")


if __name__ == "__main__":
    main()
