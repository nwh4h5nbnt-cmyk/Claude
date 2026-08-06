#!/usr/bin/env bash
# Convenience wrapper. The real work is in glow.py, so that there is one code
# path and it runs the same on Windows, where this shell script does not.
#
#     ./brand/glow.sh                 # uses brand/logo.png
#     ./brand/glow.sh path/to/other.png

set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if command -v python3 >/dev/null 2>&1; then
  py=python3
elif command -v python >/dev/null 2>&1; then
  py=python
else
  echo "Python 3 isn't installed, or isn't on your PATH." >&2
  exit 1
fi

exec "$py" "$here/glow.py" "$@"
