#!/usr/bin/env python3
"""Import household data from a casa project into pjtracker ``data/casa/``.

Copies bills, people, fixed bills, cars, and car maintenance (JSON + files).
Rewrites maintenance file paths from ``data/maintenance/`` to ``data/casa/maintenance/``.

Examples::

    uv run python scripts/import_casa_data.py /path/to/casa
    uv run python scripts/import_casa_data.py /path/to/casa --dry-run
    uv run python scripts/import_casa_data.py /path/to/casa --overwrite

By default, JSON files are merged (casa wins on duplicate keys). Use ``--overwrite``
to replace destination files entirely with casa copies (still rewrites maintenance paths).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, TypeVar

T = TypeVar("T")

SCRIPT_DIR = Path(__file__).resolve().parent
PJTRACKER_ROOT = SCRIPT_DIR.parent
DEST_ROOT = PJTRACKER_ROOT / "data" / "casa"

JSON_FILES = (
    "people.json",
    "fixed_bills.json",
    "bills_history.json",
    "cars.json",
)

MAINTENANCE_RECORDS_REL = Path("maintenance") / "records.json"
MAINTENANCE_FILES_REL = Path("maintenance") / "files"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _merge_people(source: list[dict], dest: list[dict]) -> list[dict]:
    by_id = {p["id"]: p for p in dest}
    for p in source:
        by_id[p["id"]] = p
    return sorted(by_id.values(), key=lambda p: p["id"])


def _merge_cars(source: list[dict], dest: list[dict]) -> list[dict]:
    by_id = {c["id"]: c for c in dest}
    for c in source:
        by_id[c["id"]] = c
    return sorted(by_id.values(), key=lambda c: c["id"])


def _month_key(record: dict) -> tuple[int, int]:
    return (int(record["year"]), int(record["month"]))


def _merge_bills_history(source: list[dict], dest: list[dict]) -> list[dict]:
    by_month = {_month_key(r): r for r in dest}
    for r in source:
        by_month[_month_key(r)] = r
    merged = list(by_month.values())
    merged.sort(key=_month_key, reverse=True)
    return merged


def _merge_fixed_bills(source: list[dict], dest: list[dict]) -> list[dict]:
    """Merge by bill name; casa (source) wins on duplicate names."""
    by_name = {b["name"]: b for b in dest}
    for b in source:
        by_name[b["name"]] = b
    return sorted(by_name.values(), key=lambda b: b["name"].lower())


def _rewrite_maintenance_path(path: str) -> str:
    if path.startswith("data/casa/maintenance/"):
        return path
    if path.startswith("data/maintenance/"):
        return "data/casa/maintenance/" + path[len("data/maintenance/") :]
    return path


def _rewrite_record_paths(record: dict) -> dict:
    out = deepcopy(record)
    source = out.get("source")
    if isinstance(source, dict) and "path" in source:
        source["path"] = _rewrite_maintenance_path(str(source["path"]))
    attachments = out.get("attachments")
    if isinstance(attachments, list):
        for att in attachments:
            if isinstance(att, dict) and "path" in att:
                att["path"] = _rewrite_maintenance_path(str(att["path"]))
    return out


def _merge_maintenance_records(source: list[dict], dest: list[dict]) -> list[dict]:
    by_id = {r["id"]: _rewrite_record_paths(r) for r in dest}
    for r in source:
        by_id[r["id"]] = _rewrite_record_paths(r)
    merged = list(by_id.values())
    merged.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return merged


def _resolve_casa_root(path: Path) -> Path:
    path = path.expanduser().resolve()
    if (path / "data" / "people.json").exists() or (path / "data" / "bills_history.json").exists():
        return path
    if path.name == "data" and path.parent.exists():
        return path.parent
    raise SystemExit(
        f"Could not find casa data under {path}. "
        "Pass the casa project root (folder containing data/people.json or data/bills_history.json)."
    )


def _copy_tree(src: Path, dest: Path, dry_run: bool) -> int:
    if not src.exists():
        return 0
    count = 0
    for file_path in src.rglob("*"):
        if not file_path.is_file():
            continue
        rel = file_path.relative_to(src)
        if ".thumbs" in rel.parts:
            continue
        target = dest / rel
        if target.exists() and target.stat().st_size == file_path.stat().st_size:
            continue
        count += 1
        if dry_run:
            print(f"  would copy file {rel}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, target)
            print(f"  copied file {rel}")
    return count


def _import_json_file(
    name: str,
    source_data_dir: Path,
    dest_dir: Path,
    merge_fn: Callable[[T, T], T],
    overwrite: bool,
    dry_run: bool,
) -> str:
    src = source_data_dir / name
    dest = dest_dir / name
    if not src.exists():
        return f"skip {name} (not in casa)"

    source_data = _load_json(src)
    if overwrite or not dest.exists():
        merged = source_data
        action = "replace" if overwrite and dest.exists() else "copy"
    else:
        dest_data = _load_json(dest)
        merged = merge_fn(source_data, dest_data)
        action = "merge"

    if dry_run:
        return f"would {action} {name}"

    _save_json(dest, merged)
    return f"{action}d {name}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import casa household data into pjtracker data/casa/."
    )
    parser.add_argument(
        "casa_path",
        type=Path,
        help="Path to casa project root (or its data/ folder)",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEST_ROOT,
        help=f"Destination directory (default: {DEST_ROOT})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without writing files",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace JSON files with casa copies instead of merging",
    )
    args = parser.parse_args()

    casa_root = _resolve_casa_root(args.casa_path)
    source_data = casa_root / "data"
    dest_dir = args.dest.expanduser().resolve()

    if not source_data.is_dir():
        print(f"error: missing source data directory {source_data}", file=sys.stderr)
        return 1

    print(f"casa root:   {casa_root}")
    print(f"destination: {dest_dir}")
    if args.dry_run:
        print("mode: dry-run")
    if args.overwrite:
        print("mode: overwrite JSON (no merge)")

    if not args.dry_run:
        dest_dir.mkdir(parents=True, exist_ok=True)

    results: list[str] = []

    results.append(
        _import_json_file(
            "people.json",
            source_data,
            dest_dir,
            _merge_people,
            args.overwrite,
            args.dry_run,
        )
    )
    results.append(
        _import_json_file(
            "fixed_bills.json",
            source_data,
            dest_dir,
            _merge_fixed_bills,
            args.overwrite,
            args.dry_run,
        )
    )
    results.append(
        _import_json_file(
            "bills_history.json",
            source_data,
            dest_dir,
            _merge_bills_history,
            args.overwrite,
            args.dry_run,
        )
    )
    results.append(
        _import_json_file(
            "cars.json",
            source_data,
            dest_dir,
            _merge_cars,
            args.overwrite,
            args.dry_run,
        )
    )

    # maintenance records.json
    src_records = source_data / MAINTENANCE_RECORDS_REL
    dest_records = dest_dir / MAINTENANCE_RECORDS_REL
    if src_records.exists():
        source_records = _load_json(src_records)
        if args.overwrite or not dest_records.exists():
            merged_records = [_rewrite_record_paths(r) for r in source_records]
            action = "replace" if args.overwrite and dest_records.exists() else "copy"
        else:
            dest_records_data = _load_json(dest_records)
            merged_records = _merge_maintenance_records(source_records, dest_records_data)
            action = "merge"
        if args.dry_run:
            results.append(f"would {action} maintenance/records.json")
        else:
            _save_json(dest_records, merged_records)
            results.append(f"{action}d maintenance/records.json")
    else:
        results.append("skip maintenance/records.json (not in casa)")

    src_files = source_data / MAINTENANCE_FILES_REL
    dest_files = dest_dir / MAINTENANCE_FILES_REL
    if src_files.exists():
        print("maintenance files:")
        copied = _copy_tree(src_files, dest_files, args.dry_run)
        results.append(
            f"{'would copy' if args.dry_run else 'copied'} {copied} maintenance file(s)"
        )
    else:
        results.append("skip maintenance/files/ (not in casa)")

    print("\nSummary:")
    for line in results:
        print(f"  {line}")

    if args.dry_run:
        print("\n(dry-run — no files written)")
    else:
        print("\nDone. Restart pjtracker API if it is running.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
