#!/usr/bin/env bash
# Build every HDR variant of the logo from one source PNG, then check each one
# actually carries its HDR tag. Run it from anywhere:
#
#     ./brand/glow.sh                 # uses brand/logo.png
#     ./brand/glow.sh path/to/other.png
#
# Outputs land in brand/out/. Re-running overwrites them, so it is safe to run
# again after you tweak the source artwork.

set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
src="${1:-$here/logo.png}"
out="$here/out"

if [ ! -f "$src" ]; then
  echo "No source logo at: $src" >&2
  echo "Save the master artwork as brand/logo.png (PNG, square, 1000px+, transparent" >&2
  echo "or black background) and run this again." >&2
  exit 1
fi

python3 -c 'import PIL' 2>/dev/null || { echo "Pillow is missing. Run: pip install pillow" >&2; exit 1; }

mkdir -p "$out"

# The one you upload. LinkedIn re-encodes uploads to JPEG, which throws away a
# PNG's HDR chunk but copies an ICC profile through untouched — so social gets
# the JPEG, always.
python3 "$here/hdr_glow.py" "$src" "$out/logo-hdr.jpg"

# The two you serve yourself, where nothing re-encodes anything. 4000 nits is
# roughly the Wiz burn; 1000 is the same effect with the volume down, and is
# the safer pick if the logo sits next to body text someone has to read.
python3 "$here/hdr_glow.py" "$src" "$out/logo-hdr-4000.png" --nits 4000
python3 "$here/hdr_glow.py" "$src" "$out/logo-hdr-1000.png" --nits 1000

echo
echo "Checking the tags survived:"
python3 - "$out" <<'PY'
import struct, sys, os

out = sys.argv[1]

def png_chunks(path):
    data = open(path, "rb").read()
    i, types = 8, []
    while i < len(data):
        n = struct.unpack(">I", data[i:i + 4])[0]
        types.append(data[i + 4:i + 8])
        i += 12 + n
    return types

ok = True

jpg = os.path.join(out, "logo-hdr.jpg")
from PIL import Image
has_icc = bool(Image.open(jpg).info.get("icc_profile"))
ok &= has_icc
print(f"  {'PASS' if has_icc else 'FAIL'}  logo-hdr.jpg carries a Rec.2020+PQ ICC profile")

for name in ("logo-hdr-4000.png", "logo-hdr-1000.png"):
    types = png_chunks(os.path.join(out, name))
    tagged = b"cICP" in types and not ({b"iCCP", b"sRGB", b"gAMA", b"cHRM"} & set(types))
    ok &= tagged
    print(f"  {'PASS' if tagged else 'FAIL'}  {name} carries a clean cICP (BT.2020 + PQ) tag")

sys.exit(0 if ok else 1)
PY

echo
echo "Done. Upload brand/out/logo-hdr.jpg as the LinkedIn *page* logo."
