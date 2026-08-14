#!/usr/bin/env bash
# Backup pjtracker data (SQLite + pdfs/ + images/) to Google Drive via rclone.
#
# Cron example (daily 03:00):
#   0 3 * * * cd /path/to/pjtracker && ./scripts/backup.sh >> /tmp/pjtracker-backup.log 2>&1
#
# Env:
#   RCLONE_REMOTE   rclone remote name (default: gdrive)
#   RCLONE_PATH     folder on the remote (default: pjtracker-backups)
#   KEEP_N          how many remote tars to keep (default: 14; 0 = no prune)
#   KEEP_LOCAL      set to 1 to keep the local tar after upload
#   PJTRACKER_DB_PATH  override DB path (pdfs/ and images/ live next to it)
#   BACKUP_SSH_HOST hostname shown in the local-only scp hint (default: <hostname>.local)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive}"
RCLONE_PATH="${RCLONE_PATH:-pjtracker-backups}"
KEEP_N="${KEEP_N:-14}"
KEEP_LOCAL="${KEEP_LOCAL:-0}"

DRY_RUN=0
LOCAL_ONLY=0

usage() {
  cat <<'EOF'
Usage: backup.sh [--dry-run] [--local-only] [-h|--help]

  --dry-run      Build the tar.gz; do not upload or prune
  --local-only   Build the tar.gz and keep it locally; skip rclone
  -h, --help     Show this help

Environment:
  RCLONE_REMOTE      rclone remote (default: gdrive)
  RCLONE_PATH        remote folder (default: pjtracker-backups)
  KEEP_N             remote tars to keep (default: 14; 0 = no prune)
  KEEP_LOCAL         1 to keep local tar after upload (default: 0)
  PJTRACKER_DB_PATH  override path to pjtracker.db
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --local-only) LOCAL_ONLY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -n "${PJTRACKER_DB_PATH:-}" ]]; then
  DB_PATH="$(cd "$(dirname "${PJTRACKER_DB_PATH}")" && pwd)/$(basename "${PJTRACKER_DB_PATH}")"
else
  DB_PATH="$ROOT/pjtracker.db"
fi
DATA_ROOT="$(dirname "$DB_PATH")"
PDF_DIR="$DATA_ROOT/pdfs"
IMAGES_DIR="$DATA_ROOT/images"

for cmd in sqlite3 tar; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "error: required command not found: $cmd" >&2
    exit 1
  fi
done

if [[ ! -f "$DB_PATH" ]]; then
  echo "error: database not found: $DB_PATH" >&2
  exit 1
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
ARCHIVE_NAME="pjtracker-${STAMP}.tar.gz"
WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/pjtracker-backup.XXXXXX")"
cleanup() {
  rm -rf "$WORKDIR"
}
trap cleanup EXIT

STAGING="$WORKDIR/staging"
mkdir -p "$STAGING"

echo "Snapshotting SQLite: $DB_PATH"
sqlite3 "$DB_PATH" ".backup '$STAGING/pjtracker.db'"

# Write archive to data root for --dry-run / --local-only / KEEP_LOCAL; else temp
if [[ "$LOCAL_ONLY" -eq 1 || "$KEEP_LOCAL" -eq 1 || "$DRY_RUN" -eq 1 ]]; then
  ARCHIVE_PATH="$DATA_ROOT/$ARCHIVE_NAME"
else
  ARCHIVE_PATH="$WORKDIR/$ARCHIVE_NAME"
fi

echo "Creating archive: $ARCHIVE_PATH"
TAR_CMD=(tar -czf "$ARCHIVE_PATH" -C "$STAGING" pjtracker.db)
if [[ -d "$PDF_DIR" ]]; then
  TAR_CMD+=(-C "$DATA_ROOT" pdfs)
else
  echo "warning: pdfs/ not found at $PDF_DIR (skipping)" >&2
fi
if [[ -d "$IMAGES_DIR" ]]; then
  TAR_CMD+=(-C "$DATA_ROOT" images)
else
  echo "warning: images/ not found at $IMAGES_DIR (skipping)" >&2
fi
"${TAR_CMD[@]}"

ARCHIVE_SIZE="$(du -h "$ARCHIVE_PATH" | awk '{print $1}')"
echo "Archive size: $ARCHIVE_SIZE"

report_local_archive() {
  local host="${BACKUP_SSH_HOST:-}"
  if [[ -z "$host" ]]; then
    host="$(hostname 2>/dev/null || echo localhost)"
    # mDNS on LAN (e.g. raspi -> raspi.local) unless already a FQDN/IP-ish name
    if [[ "$host" != *.* ]]; then
      host="${host}.local"
    fi
  fi
  echo ""
  echo "Archive ready (not uploaded):"
  echo "  $ARCHIVE_PATH"
  echo ""
  echo "Download it from another machine with:"
  echo "  scp $(whoami)@${host}:'$ARCHIVE_PATH' ."
  echo ""
}

if [[ "$DRY_RUN" -eq 1 ]]; then
  report_local_archive
  exit 0
fi

if [[ "$LOCAL_ONLY" -eq 1 ]]; then
  report_local_archive
  exit 0
fi

if ! command -v rclone >/dev/null 2>&1; then
  echo "error: rclone not found (install rclone or use --local-only)" >&2
  exit 1
fi

REMOTE_DEST="${RCLONE_REMOTE}:${RCLONE_PATH}"
echo "Uploading to $REMOTE_DEST/"
rclone copy "$ARCHIVE_PATH" "$REMOTE_DEST/" --progress

if [[ "$KEEP_LOCAL" -ne 1 ]]; then
  if [[ "$ARCHIVE_PATH" != "$WORKDIR"* ]]; then
    rm -f "$ARCHIVE_PATH"
  fi
  echo "Removed local archive (set KEEP_LOCAL=1 to keep)."
else
  echo "Kept local archive at $ARCHIVE_PATH"
fi

# Prune old remote backups, keeping the newest KEEP_N
if [[ "$KEEP_N" =~ ^[0-9]+$ ]] && [[ "$KEEP_N" -gt 0 ]]; then
  echo "Pruning remote backups (keeping newest $KEEP_N)..."
  REMOTE_FILES=()
  while IFS= read -r line; do
    [[ -n "$line" ]] || continue
    REMOTE_FILES+=("$line")
  done < <(
    rclone lsf "$REMOTE_DEST" --files-only 2>/dev/null \
      | grep -E '^pjtracker-[0-9]{8}-[0-9]{6}\.tar\.gz$' \
      | sort -r
  ) || true

  count="${#REMOTE_FILES[@]}"
  if [[ "$count" -gt "$KEEP_N" ]]; then
    i="$KEEP_N"
    while [[ "$i" -lt "$count" ]]; do
      old="${REMOTE_FILES[$i]}"
      echo "  deleting $REMOTE_DEST/$old"
      rclone deletefile "$REMOTE_DEST/$old"
      i=$((i + 1))
    done
  else
    echo "  ${count} remote backup(s); nothing to prune."
  fi
elif [[ "$KEEP_N" == "0" ]]; then
  echo "KEEP_N=0: skipping remote prune."
else
  echo "warning: invalid KEEP_N=$KEEP_N (skipping prune)" >&2
fi

echo "Backup complete."
