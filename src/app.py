"""Nota Fiscal Tracker – shared DB and helpers (Home and pages import from here)."""

import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "pjtracker.db"
PDF_DIR = Path(__file__).resolve().parent.parent / "pdfs"
IMAGES_DIR = Path(__file__).resolve().parent.parent / "images"


def init_db() -> None:
    """Create the nf_entries table if it does not exist and ensure unique (nf_date, verification_code, usd)."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS nf_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT,
                usd REAL NOT NULL,
                rate REAL NOT NULL,
                spread REAL NOT NULL,
                brl_no_spread REAL NOT NULL,
                brl_with_spread REAL NOT NULL,
                nf_date TEXT,
                verification_code TEXT,
                payment_via TEXT,
                pdf_path TEXT,
                created_at TEXT NOT NULL
            )
        """)
        # Migration: add payment_via if table existed without it
        try:
            conn.execute("ALTER TABLE nf_entries ADD COLUMN payment_via TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
        # Migration: add pdf_path if table existed without it
        try:
            conn.execute("ALTER TABLE nf_entries ADD COLUMN pdf_path TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
        # Uniqueness: one row per NF (NULLs normalized to '' for index)
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_nf_entries_unique
            ON nf_entries (COALESCE(nf_date, ''), COALESCE(verification_code, ''), usd)
        """)
        # Attached images (clipboard etc.) per NF
        conn.execute("""
            CREATE TABLE IF NOT EXISTS nf_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nf_id INTEGER NOT NULL,
                image_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (nf_id) REFERENCES nf_entries (id)
            )
        """)


def _sanitize_filename(s: str) -> str:
    """Replace characters that are unsafe in filenames."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in s)


def save_pdf(pdf_bytes: bytes, verification_code: str, nf_date: str | None, usd: float) -> Path:
    """Save PDF to pdfs/ and return the path. Filename is unique per (date, code, usd)."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    safe_code = _sanitize_filename(verification_code or "unknown")[:50]
    safe_date = _sanitize_filename((nf_date or "").replace(" ", "_"))[:30] or "nodate"
    base = f"nf_{safe_date}_{safe_code}_{usd:.2f}"
    path = PDF_DIR / f"{base}.pdf"
    counter = 0
    while path.exists():
        counter += 1
        path = PDF_DIR / f"{base}_{counter}.pdf"
    path.write_bytes(pdf_bytes)
    return path


def save_image(image_bytes: bytes, nf_id: int, mime_or_ext: str) -> Path:
    """Save image to images/ and return the path. Filename is unique per nf_id + timestamp + counter."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    # Normalize to extension: "image/png" -> "png", "png" -> "png"
    ext = mime_or_ext.strip().lower()
    if "/" in ext:
        ext = ext.split("/", 1)[-1]
    if ext not in ("png", "jpg", "jpeg", "gif", "webp"):
        ext = "png"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    base = f"nf_{nf_id}_{ts}"
    path = IMAGES_DIR / f"{base}.{ext}"
    counter = 0
    while path.exists():
        counter += 1
        path = IMAGES_DIR / f"{base}_{counter}.{ext}"
    path.write_bytes(image_bytes)
    return path


def save_nf_image(nf_id: int, image_path: str) -> None:
    """Insert one row into nf_images."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO nf_images (nf_id, image_path, created_at) VALUES (?, ?, ?)",
            (nf_id, image_path, datetime.now(timezone.utc).isoformat()),
        )


def get_nf_images(nf_id: int) -> list[dict]:
    """Return image rows for the given NF (id, image_path, created_at)."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT id, image_path, created_at FROM nf_images WHERE nf_id = ? ORDER BY created_at ASC",
            (nf_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def save_nf_entry(
    company: str | None,
    usd: float,
    rate: float,
    spread: float,
    brl_no_spread: float,
    brl_with_spread: float,
    nf_date: str | None,
    verification_code: str | None,
    payment_via: str | None,
    pdf_path: str | None = None,
) -> tuple[bool, int]:
    """Insert one NF entry; skip if (nf_date, verification_code, usd) already exists.
    Returns (inserted, nf_id): inserted is True if a new row was added, nf_id is the row id in both cases."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO nf_entries (
                company, usd, rate, spread, brl_no_spread, brl_with_spread,
                nf_date, verification_code, payment_via, pdf_path, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                company,
                usd,
                rate,
                spread,
                brl_no_spread,
                brl_with_spread,
                nf_date,
                verification_code,
                payment_via,
                pdf_path,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        inserted = cur.rowcount > 0
        if inserted:
            nf_id = cur.lastrowid
        else:
            row = conn.execute(
                "SELECT id FROM nf_entries WHERE COALESCE(nf_date, '') = ? AND COALESCE(verification_code, '') = ? AND usd = ?",
                (nf_date or "", verification_code or "", usd),
            ).fetchone()
            nf_id = row[0] if row else 0
        return (inserted, nf_id)


def parse_nf_date_to_date(nf_date: str | None) -> date | None:
    """Parse nf_date 'DD/MM/YYYY HH:MM:SS' to a date for filtering. Returns None if invalid or empty."""
    if not nf_date or not nf_date.strip():
        return None
    try:
        dt = datetime.strptime(nf_date.strip().split()[0], "%d/%m/%Y")
        return dt.date()
    except (ValueError, IndexError):
        return None


def get_nf_entries(
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict]:
    """Return NF entries, optionally filtered by nf_date range. Newest first. Each row is a dict."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT * FROM nf_entries ORDER BY created_at DESC",
        )
        rows = [dict(r) for r in cur.fetchall()]

    if date_from is None and date_to is None:
        return rows

    filtered = []
    for row in rows:
        d = parse_nf_date_to_date(row.get("nf_date"))
        if d is None:
            continue
        if date_from is not None and d < date_from:
            continue
        if date_to is not None and d > date_to:
            continue
        filtered.append(row)
    return filtered
