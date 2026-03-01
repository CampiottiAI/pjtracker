"""Nota Fiscal Tracker – shared DB and helpers (Home and pages import from here)."""

import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "pjtracker.db"
PDF_DIR = Path(__file__).resolve().parent.parent / "pdfs"


def init_db() -> None:
    """Create the nf_entries table if it does not exist and ensure unique (nf_date, verification_code, usd)."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
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
) -> bool:
    """Insert one NF entry; skip if (nf_date, verification_code, usd) already exists. Returns True if inserted."""
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
        return cur.rowcount > 0


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
