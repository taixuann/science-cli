#!/usr/bin/env bash
set -euo pipefail

# Make paths completely relative and portable
DST="$(cd "$(dirname "$0")" && pwd)"
SRC="$(cd "$(dirname "$0")/.." && pwd)"

echo "Copying dashboard from $SRC to $DST"

# Copy main dashboard
mkdir -p "$DST/results"
cp "$SRC/results/dashboard.html" "$DST/results/dashboard.html"
echo "  → results/dashboard.html"

# Copy per-protocol dashboard files + data_*.js
while IFS= read -r -d '' f; do
    rel="${f#$SRC/}"
    mkdir -p "$DST/$(dirname "$rel")"
    cp "$f" "$DST/$rel"
    echo "  → $rel"
done < <(find "$SRC/protocol" -path "*/results/dashboard.html" -print0)

while IFS= read -r -d '' f; do
    rel="${f#$SRC/}"
    mkdir -p "$DST/$(dirname "$rel")"
    cp "$f" "$DST/$rel"
    echo "  → $rel"
done < <(find "$SRC/protocol" -path "*/results/data_*.js" -print0)

echo "Done. Run: git add . && git commit -m 'update dashboard' && git push"
