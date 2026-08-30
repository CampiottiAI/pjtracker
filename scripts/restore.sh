#!/usr/bin/env bash
# Restore pjtracker data (SQLite + pdfs/ + images/) from a backup.sh archive
# into the current working directory (or PJTRACKER_DB_PATH parent).
#
# Stop the API/UI before restoring. SQLite WAL files next to the DB are removed
# after replace so they cannot replay onto the restored snapshot.
#
# Env:
#   PJTRACKER_DB_PATH  restore next to this DB path instead of $PWD
#   RCLONE_REMOTE      rclone remote name (default: gdrive)
#   RCLONE_PATH        folder on the remote (default: pjtracker-backups)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$(pwd)"

RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive}"
RCLONE_PATH="${RCLONE_PATH:-pjtracker-backups}"

DRY_RUN=0
FORCE=0
LATEST=0
FROM_REMOTE=0
ARCHIVE=""

usage() {
  cat <<'EOF'
Usage: restore.sh [archive.tar.gz] [--latest] [--from-remote] [--dry-run] [--force] [-h|--help]

Restore a backup.sh archive into the current directory (pjtracker.db, pdfs/, images/).

  archive.tar.gz   Local archive created by backup.sh
  --latest         Use the newest local pjtracker-YYYYMMDD-HHMMSS.tar.gz
                   (searches the destination, then the repo root)
  --from-remote    Download from rclone (latest, or ARCHIVE as the remote filename)
  --dry-run        Show what would be restored; do not write
  --force          Overwrite without confirmation
  -h, --help       Show this help

Environment:
  PJTRACKER_DB_PATH  restore next to this DB (pdfs/ and images/ live next to it)
  RCLONE_REMOTE      rclone remote (default: gdrive)
  RCLONE_PATH        remote folder (default: pjtracker-backups)

Examples:
  ./scripts/restore.sh pjtracker-20260830-030000.tar.gz
  ./scripts/restore.sh --latest
  ./scripts/restore.sh --from-remote
  ./scripts/restore.sh --from-remote --dry-run
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --force) FORCE=1; shift ;;
    --latest) LATEST=1; shift ;;
    --from-remote) FROM_REMOTE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    -*)
      echo "error: unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
    *)
      if [[ -n "$ARCHIVE" ]]; then
        echo "error: unexpected extra argument: $1" >&2
        usage >&2
        exit 1
      fi
      ARCHIVE="$1"
      shift
      ;;
  esac
done

if [[ -n "${PJTRACKER_DB_PATH:-}" ]]; then
  DB_PATH="$(cd "$(dirname "${PJTRACKER_DB_PATH}")" && pwd)/$(basename "${PJTRACKER_DB_PATH}")"
  DEST="$(dirname "$DB_PATH")"
else
  DB_PATH="$DEST/pjtracker.db"
fi
PDF_DIR="$DEST/pdfs"
IMAGES_DIR="$DEST/images"

ARCHIVE_NAME_RE='^pjtracker-[0-9]{8}-[0-9]{6}\.tar\.gz$'

list_local_archives() {
  local dir="$1"
  local matches=()
  local f
  shopt -s nullglob
  matches=("$dir"/pjtracker-[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9].tar.gz)
  shopt -u nullglob
  if [[ ${#matches[@]} -eq 0 ]]; then
    return 0
  fi
  printf '%s\n' "${matches[@]}" | sort -r
}

newest_local_archive() {
  local f
  f="$(list_local_archives "$DEST" | head -n 1 || true)"
  if [[ -n "$f" ]]; then
    printf '%s\n' "$f"
    return 0
  fi
  if [[ "$DEST" != "$ROOT" ]]; then
    f="$(list_local_archives "$ROOT" | head -n 1 || true)"
    if [[ -n "$f" ]]; then
      printf '%s\n' "$f"
      return 0
    fi
  fi
  return 1
}

newest_remote_archive() {
  rclone lsf "${RCLONE_REMOTE}:${RCLONE_PATH}" --files-only 2>/dev/null \
    | grep -E "$ARCHIVE_NAME_RE" \
    | sort -r \
    | head -n 1
}

member_allowed() {
  local member="${1#./}"
  case "$member" in
    pjtracker.db|pdfs|pdfs/|pdfs/*|images|images/|images/*) return 0 ;;
    *) return 1 ;;
  esac
}

validate_archive_members() {
  local archive="$1"
  local member
  local has_db=0
  while IFS= read -r member; do
    [[ -n "$member" ]] || continue
    if ! member_allowed "$member"; then
      echo "error: archive contains unexpected path: $member" >&2
      echo "Expected only pjtracker.db, pdfs/, and images/ (backup.sh format)." >&2
      exit 1
    fi
    local stripped="${member#./}"
    if [[ "$stripped" == "pjtracker.db" ]]; then
      has_db=1
    fi
  done < <(tar -tzf "$archive")
  if [[ "$has_db" -ne 1 ]]; then
    echo "error: archive is missing pjtracker.db: $archive" >&2
    exit 1
  fi
}

archive_has_prefix() {
  local archive="$1"
  local prefix="$2"
  local member
  while IFS= read -r member; do
    member="${member#./}"
    case "$member" in
      "$prefix"|"$prefix"/*|"$prefix"/) return 0 ;;
    esac
  done < <(tar -tzf "$archive")
  return 1
}

confirm_overwrite() {
  if [[ "$FORCE" -eq 1 || "$DRY_RUN" -eq 1 ]]; then
    return 0
  fi
  if [[ ! -t 0 ]]; then
    echo "error: destination already has data; pass --force to overwrite (stdin is not a TTY)" >&2
    exit 1
  fi
  local reply
  read -r -p "Overwrite existing data in $DEST? [y/N] " reply
  case "$reply" in
    y|Y|yes|YES) return 0 ;;
    *) echo "Aborted."; exit 1 ;;
  esac
}

WORKDIR=""
cleanup() {
  if [[ -n "$WORKDIR" && -d "$WORKDIR" ]]; then
    rm -rf "$WORKDIR"
  fi
}
trap cleanup EXIT

if [[ "$FROM_REMOTE" -eq 1 ]]; then
  if ! command -v rclone >/dev/null 2>&1; then
    echo "error: rclone not found (needed for --from-remote)" >&2
    exit 1
  fi
  REMOTE_DEST="${RCLONE_REMOTE}:${RCLONE_PATH}"
  remote_name=""
  if [[ -n "$ARCHIVE" ]]; then
    remote_name="$(basename "$ARCHIVE")"
  else
    remote_name="$(newest_remote_archive || true)"
  fi
  if [[ -z "$remote_name" ]]; then
    echo "error: no pjtracker-YYYYMMDD-HHMMSS.tar.gz found on $REMOTE_DEST" >&2
    exit 1
  fi
  if [[ ! "$remote_name" =~ $ARCHIVE_NAME_RE ]]; then
    echo "error: remote name is not a backup.sh archive: $remote_name" >&2
    exit 1
  fi
  echo "Remote archive: $REMOTE_DEST/$remote_name"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    ARCHIVE=""
    REMOTE_ONLY_NAME="$remote_name"
  else
    WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/pjtracker-restore.XXXXXX")"
    echo "Downloading $remote_name..."
    rclone copyto "$REMOTE_DEST/$remote_name" "$WORKDIR/$remote_name" --progress
    ARCHIVE="$WORKDIR/$remote_name"
  fi
elif [[ "$LATEST" -eq 1 ]]; then
  if [[ -n "$ARCHIVE" ]]; then
    echo "error: pass either --latest or an archive path, not both" >&2
    exit 1
  fi
  ARCHIVE="$(newest_local_archive || true)"
  if [[ -z "$ARCHIVE" ]]; then
    echo "error: no local pjtracker-YYYYMMDD-HHMMSS.tar.gz in $DEST or $ROOT" >&2
    echo "Use --from-remote to download the latest rclone backup." >&2
    exit 1
  fi
else
  if [[ -z "$ARCHIVE" ]]; then
    echo "error: provide an archive path, --latest, or --from-remote" >&2
    usage >&2
    exit 1
  fi
  if [[ "$ARCHIVE" != /* ]]; then
    ARCHIVE="$DEST/$ARCHIVE"
  fi
fi

if [[ "$FROM_REMOTE" -eq 1 && "$DRY_RUN" -eq 1 ]]; then
  echo "Dry-run: would download and restore $REMOTE_DEST/$REMOTE_ONLY_NAME into $DEST"
  echo "  $DEST/pjtracker.db"
  echo "  $DEST/pdfs/ (if present in archive)"
  echo "  $DEST/images/ (if present in archive)"
  exit 0
fi

if [[ ! -f "$ARCHIVE" ]]; then
  echo "error: archive not found: $ARCHIVE" >&2
  exit 1
fi

validate_archive_members "$ARCHIVE"

HAS_PDFS=0
HAS_IMAGES=0
if archive_has_prefix "$ARCHIVE" "pdfs"; then
  HAS_PDFS=1
fi
if archive_has_prefix "$ARCHIVE" "images"; then
  HAS_IMAGES=1
fi

echo "Archive:     $ARCHIVE"
echo "Destination: $DEST"
echo "Will restore:"
echo "  $DB_PATH"
if [[ "$HAS_PDFS" -eq 1 ]]; then
  echo "  $PDF_DIR/"
else
  echo "  pdfs/ not in archive (leave existing)"
fi
if [[ "$HAS_IMAGES" -eq 1 ]]; then
  echo "  $IMAGES_DIR/"
else
  echo "  images/ not in archive (leave existing)"
fi

EXISTING=0
if [[ -e "$DB_PATH" || -d "$PDF_DIR" || -d "$IMAGES_DIR" ]]; then
  EXISTING=1
fi
if [[ "$EXISTING" -eq 1 ]]; then
  confirm_overwrite
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo ""
  echo "Archive contents:"
  tar -tzf "$ARCHIVE"
  echo ""
  echo "Dry-run: no files written."
  exit 0
fi

if [[ -z "$WORKDIR" ]]; then
  WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/pjtracker-restore.XXXXXX")"
fi
EXTRACT="$WORKDIR/extract"
mkdir -p "$EXTRACT"
tar -xzf "$ARCHIVE" -C "$EXTRACT"

RESTAGED_DB="$EXTRACT/pjtracker.db"
if [[ ! -f "$RESTAGED_DB" && -f "$EXTRACT/./pjtracker.db" ]]; then
  RESTAGED_DB="$EXTRACT/./pjtracker.db"
fi
if [[ ! -f "$RESTAGED_DB" ]]; then
  echo "error: extract did not produce pjtracker.db" >&2
  exit 1
fi

mkdir -p "$DEST"
echo "Replacing $DB_PATH"
mv -f "$RESTAGED_DB" "$DB_PATH"
rm -f "${DB_PATH}-wal" "${DB_PATH}-shm"

if [[ "$HAS_PDFS" -eq 1 ]]; then
  echo "Replacing $PDF_DIR/"
  rm -rf "$PDF_DIR"
  mv "$EXTRACT/pdfs" "$PDF_DIR"
fi
if [[ "$HAS_IMAGES" -eq 1 ]]; then
  echo "Replacing $IMAGES_DIR/"
  rm -rf "$IMAGES_DIR"
  mv "$EXTRACT/images" "$IMAGES_DIR"
fi

echo "Restore complete. Start the app with ./scripts/dev.sh or ./scripts/prod.sh."
