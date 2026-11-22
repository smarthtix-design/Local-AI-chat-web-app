#!/bin/bash
# Backs up chroma_db, stats.db and documents into backups/, keeping the newest KEEP archives.
PROJECT="${PROJECT:-$(cd "$(dirname "$0")/.." && pwd)}"
KEEP="${KEEP:-7}"
mkdir -p "$PROJECT/backups"
OUT="$PROJECT/backups/tinychat-${STAMP:-$(date +%Y%m%d-%H%M%S)}.tgz"
cd "$PROJECT" || exit 1
tar czf "$OUT" $(for x in chroma_db stats.db documents; do [ -e "$x" ] && echo "$x"; done) 2>/dev/null && echo "backup written: $OUT"
ls -1 "$PROJECT"/backups/tinychat-*.tgz 2>/dev/null | sort | head -n -"$KEEP" | xargs -r rm -f
