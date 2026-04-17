#!/usr/bin/env bash
# decode-url.sh — Decode a kroki URL back to diagram source.
#
# Usage:
#   decode-url.sh '<kroki url>'
#
# Inverse of encode-url.sh: strips the URL prefix, reverses the URL-safe
# base64 substitution, decompresses with zlib. Prints source to stdout.
#
# Exit codes:
#   0 — source printed to stdout
#   2 — URL malformed or decoding failed
#   3 — usage error

set -euo pipefail

usage() {
    echo "Usage: decode-url.sh '<kroki url>'" >&2
    exit 3
}

if [[ $# -ne 1 ]]; then
    usage
fi

case "$1" in
    --help|-h) usage ;;
esac

URL="$1"

# Extract the encoded payload — last path segment after the final /
ENCODED="${URL##*/}"

if [[ -z "$ENCODED" ]]; then
    echo "Error: no encoded payload found in URL." >&2
    exit 2
fi

# Decode via Python (reverse of encode-url.sh)
SOURCE=$(printf '%s' "$ENCODED" | python3 -c '
import sys, zlib, base64
encoded = sys.stdin.read().strip()
# Re-pad to a multiple of 4
pad = "=" * (-len(encoded) % 4)
try:
    compressed = base64.urlsafe_b64decode(encoded + pad)
    data = zlib.decompress(compressed)
    sys.stdout.write(data.decode("utf-8"))
except (ValueError, zlib.error, UnicodeDecodeError) as e:
    sys.stderr.write(f"decode failed: {e}\n")
    sys.exit(1)
') || {
    echo "Error: decoding failed for URL." >&2
    exit 2
}

printf '%s' "$SOURCE"
# Trailing newline only if not already present
[[ "${SOURCE: -1}" == $'\n' ]] || echo
