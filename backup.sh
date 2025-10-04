#!/usr/bin/env bash
set -euo pipefail

SRC_DIR=${SRC_DIR:-/data}
DEST_DIR=${DEST_DIR:-/backup}
REMOTE=${REMOTE:-}                    # e.g. user@host:/path  (leave empty for local)
RSYNC_OPTS=${RSYNC_OPTS:--a --delete} # tweak as needed; add -z for remote compression

echo "[$(date -u +%FT%TZ)] Starting dayplanner backup…"
if [[ -n "$REMOTE" ]]; then
  echo "→ rsync to remote: $REMOTE"
  rsync $RSYNC_OPTS "$SRC_DIR"/ "$REMOTE"/
else
  echo "→ rsync to local: $DEST_DIR"
  mkdir -p "$DEST_DIR"
  rsync $RSYNC_OPTS "$SRC_DIR"/ "$DEST_DIR"/
fi
echo "[$(date -u +%FT%TZ)] Done."