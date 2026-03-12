"""Nota Fiscal Tracker – shared DB and helpers (Home and pages import from here)."""

import hashlib
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
        # Boletos: bill PDF + optional receipt image
        conn.execute("""
            CREATE TABLE IF NOT EXISTS boletos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pdf_path TEXT NOT NULL,
                receipt_path TEXT,
                value REAL,
                emission_date TEXT,
                deadline_date TEXT,
                receipt_date TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT
            )
        """)
        # Migration: add content_hash for duplicate detection (value + emission_date + deadline_date)
        try:
            conn.execute("ALTER TABLE boletos ADD COLUMN content_hash TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_boletos_content_hash
            ON boletos (content_hash) WHERE content_hash IS NOT NULL
        """)
        # DARFs: DARF PDF + optional receipt image
        conn.execute("""
            CREATE TABLE IF NOT EXISTS darfs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pdf_path TEXT NOT NULL,
                receipt_path TEXT,
                value REAL,
                emission_date TEXT,
                deadline_date TEXT,
                receipt_date TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT
            )
        """)
        # Migration: add content_hash for duplicate detection (value + emission_date + deadline_date)
        try:
            conn.execute("ALTER TABLE darfs ADD COLUMN content_hash TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_darfs_content_hash
            ON darfs (content_hash) WHERE content_hash IS NOT NULL
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


# --- Boletos ---


def compute_boleto_content_hash(
    value: float | None,
    emission_date: str | None,
    deadline_date: str | None,
) -> str | None:
    """Deterministic hash from value and dates. Returns None if all three are missing."""
    val_str = f"{value:.2f}" if value is not None else "0"
    em = (emission_date or "").strip()
    dl = (deadline_date or "").strip()
    payload = f"{val_str}|{em}|{dl}"
    if payload == "0||":
        return None
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def save_boleto_pdf(pdf_bytes: bytes, emission_date: str | None = None, value: float | None = None) -> Path:
    """Save boleto PDF to pdfs/ with unique name. Returns path (relative to project root or absolute)."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    safe_date = _sanitize_filename((emission_date or "").replace("/", "-"))[:20] or "nodate"
    val_part = f"{value:.2f}" if value is not None else "0"
    base = f"boleto_{safe_date}_{val_part}"
    path = PDF_DIR / f"{base}.pdf"
    counter = 0
    while path.exists():
        counter += 1
        path = PDF_DIR / f"{base}_{counter}.pdf"
    path.write_bytes(pdf_bytes)
    return path


def save_boleto_receipt(boleto_id: int, image_bytes: bytes, mime_or_ext: str) -> Path:
    """Save receipt image for a boleto. Returns path."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    ext = mime_or_ext.strip().lower()
    if "/" in ext:
        ext = ext.split("/", 1)[-1]
    if ext not in ("png", "jpg", "jpeg", "gif", "webp"):
        ext = "png"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    base = f"boleto_receipt_{boleto_id}_{ts}"
    path = IMAGES_DIR / f"{base}.{ext}"
    counter = 0
    while path.exists():
        counter += 1
        path = IMAGES_DIR / f"{base}_{counter}.{ext}"
    path.write_bytes(image_bytes)
    return path


def save_boleto_entry(
    pdf_path: str,
    value: float | None = None,
    emission_date: str | None = None,
    deadline_date: str | None = None,
    receipt_path: str | None = None,
    receipt_date: str | None = None,
) -> tuple[bool, int | None]:
    """Insert one boleto row. Returns (inserted, id): (True, id) on success, (False, None) if duplicate (same value + dates)."""
    content_hash = compute_boleto_content_hash(value, emission_date, deadline_date)
    now = datetime.now(timezone.utc).isoformat()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute(
                """
                INSERT INTO boletos (
                    pdf_path, receipt_path, value, emission_date, deadline_date,
                    receipt_date, created_at, updated_at, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (pdf_path, receipt_path, value, emission_date, deadline_date, receipt_date, now, now, content_hash),
            )
            return (True, cur.lastrowid)
    except sqlite3.IntegrityError:
        return (False, None)


def boleto_exists_with_hash(content_hash: str | None) -> bool:
    """Return True if a boleto with this content_hash already exists."""
    if not content_hash:
        return False
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT 1 FROM boletos WHERE content_hash = ? LIMIT 1", (content_hash,))
        return cur.fetchone() is not None


def get_boletos() -> list[dict]:
    """Return all boletos, newest first."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT * FROM boletos ORDER BY created_at DESC",
        )
        return [dict(r) for r in cur.fetchall()]


def get_boleto_by_id(boleto_id: int) -> dict | None:
    """Return one boleto by id or None."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM boletos WHERE id = ?", (boleto_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def update_boleto_pdf(
    boleto_id: int,
    pdf_bytes: bytes,
    value: float | None,
    emission_date: str | None,
    deadline_date: str | None,
) -> bool:
    """Replace boleto PDF and update parsed fields. Keeps receipt_path/receipt_date unchanged.
    Returns True on success, False if another boleto already has the same (value, emission_date, deadline_date)."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    row = get_boleto_by_id(boleto_id)
    if not row:
        return False
    old_path = row.get("pdf_path")
    if old_path:
        full_old = Path(DB_PATH).resolve().parent / old_path if not Path(old_path).is_absolute() else Path(old_path)
        if full_old.exists():
            full_old.unlink(missing_ok=True)
    new_path = save_boleto_pdf(pdf_bytes, emission_date, value)
    path_str = str(new_path)
    content_hash = compute_boleto_content_hash(value, emission_date, deadline_date)
    now = datetime.now(timezone.utc).isoformat()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                UPDATE boletos SET pdf_path = ?, value = ?, emission_date = ?, deadline_date = ?, content_hash = ?, updated_at = ?
                WHERE id = ?
                """,
                (path_str, value, emission_date, deadline_date, content_hash, now, boleto_id),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def update_boleto_receipt(boleto_id: int, receipt_path: str, receipt_date: str | None) -> None:
    """Set receipt path and date for a boleto."""
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE boletos SET receipt_path = ?, receipt_date = ?, updated_at = ? WHERE id = ?",
            (receipt_path, receipt_date, now, boleto_id),
        )


def delete_boleto(boleto_id: int) -> bool:
    """Delete boleto row and its PDF and receipt files. Returns True if deleted, False if not found."""
    row = get_boleto_by_id(boleto_id)
    if not row:
        return False
    project_root = Path(DB_PATH).resolve().parent
    for path_key in ("pdf_path", "receipt_path"):
        raw = row.get(path_key)
        if not raw or (isinstance(raw, str) and not raw.strip()):
            continue
        p = Path(raw)
        if not p.is_absolute():
            p = project_root / raw
        if p.exists():
            p.unlink(missing_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM boletos WHERE id = ?", (boleto_id,))
    return True


# --- DARFs ---


def compute_darf_content_hash(
    value: float | None,
    emission_date: str | None,
    deadline_date: str | None,
) -> str | None:
    """Deterministic hash from value and dates. Returns None if all three are missing."""
    val_str = f"{value:.2f}" if value is not None else "0"
    em = (emission_date or "").strip()
    dl = (deadline_date or "").strip()
    payload = f"{val_str}|{em}|{dl}"
    if payload == "0||":
        return None
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def save_darf_pdf(
    pdf_bytes: bytes, emission_date: str | None = None, value: float | None = None
) -> Path:
    """Save DARF PDF to pdfs/ with unique name. Returns path."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    safe_date = _sanitize_filename((emission_date or "").replace("/", "-"))[:20] or "nodate"
    val_part = f"{value:.2f}" if value is not None else "0"
    base = f"darf_{safe_date}_{val_part}"
    path = PDF_DIR / f"{base}.pdf"
    counter = 0
    while path.exists():
        counter += 1
        path = PDF_DIR / f"{base}_{counter}.pdf"
    path.write_bytes(pdf_bytes)
    return path


def save_darf_receipt(darf_id: int, image_bytes: bytes, mime_or_ext: str) -> Path:
    """Save receipt image for a DARF. Returns path."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    ext = mime_or_ext.strip().lower()
    if "/" in ext:
        ext = ext.split("/", 1)[-1]
    if ext not in ("png", "jpg", "jpeg", "gif", "webp"):
        ext = "png"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    base = f"darf_receipt_{darf_id}_{ts}"
    path = IMAGES_DIR / f"{base}.{ext}"
    counter = 0
    while path.exists():
        counter += 1
        path = IMAGES_DIR / f"{base}_{counter}.{ext}"
    path.write_bytes(image_bytes)
    return path


def save_darf_entry(
    pdf_path: str,
    value: float | None = None,
    emission_date: str | None = None,
    deadline_date: str | None = None,
    receipt_path: str | None = None,
    receipt_date: str | None = None,
) -> tuple[bool, int | None]:
    """Insert one DARF row. Returns (inserted, id): (True, id) on success, (False, None) on duplicate."""
    content_hash = compute_darf_content_hash(value, emission_date, deadline_date)
    now = datetime.now(timezone.utc).isoformat()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute(
                """
                INSERT INTO darfs (
                    pdf_path, receipt_path, value, emission_date, deadline_date,
                    receipt_date, created_at, updated_at, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (pdf_path, receipt_path, value, emission_date, deadline_date, receipt_date, now, now, content_hash),
            )
            return (True, cur.lastrowid)
    except sqlite3.IntegrityError:
        return (False, None)


def get_darfs() -> list[dict]:
    """Return all DARFs, newest first."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT * FROM darfs ORDER BY created_at DESC",
        )
        return [dict(r) for r in cur.fetchall()]


def get_darf_by_id(darf_id: int) -> dict | None:
    """Return one DARF by id or None."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM darfs WHERE id = ?", (darf_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def update_darf_pdf(
    darf_id: int,
    pdf_bytes: bytes,
    value: float | None,
    emission_date: str | None,
    deadline_date: str | None,
) -> bool:
    """Replace DARF PDF and update parsed fields. Keeps receipt_path/receipt_date unchanged."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    row = get_darf_by_id(darf_id)
    if not row:
        return False
    old_path = row.get("pdf_path")
    if old_path:
        full_old = Path(DB_PATH).resolve().parent / old_path if not Path(old_path).is_absolute() else Path(old_path)
        if full_old.exists():
            full_old.unlink(missing_ok=True)
    new_path = save_darf_pdf(pdf_bytes, emission_date, value)
    path_str = str(new_path)
    content_hash = compute_darf_content_hash(value, emission_date, deadline_date)
    now = datetime.now(timezone.utc).isoformat()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                UPDATE darfs SET pdf_path = ?, value = ?, emission_date = ?, deadline_date = ?, content_hash = ?, updated_at = ?
                WHERE id = ?
                """,
                (path_str, value, emission_date, deadline_date, content_hash, now, darf_id),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def update_darf_receipt(darf_id: int, receipt_path: str, receipt_date: str | None) -> None:
    """Set receipt path and date for a DARF."""
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE darfs SET receipt_path = ?, receipt_date = ?, updated_at = ? WHERE id = ?",
            (receipt_path, receipt_date, now, darf_id),
        )


def delete_darf(darf_id: int) -> bool:
    """Delete DARF row and its PDF and receipt files. Returns True if deleted, False if not found."""
    row = get_darf_by_id(darf_id)
    if not row:
        return False
    project_root = Path(DB_PATH).resolve().parent
    for path_key in ("pdf_path", "receipt_path"):
        raw = row.get(path_key)
        if not raw or (isinstance(raw, str) and not raw.strip()):
            continue
        p = Path(raw)
        if not p.is_absolute():
            p = project_root / raw
        if p.exists():
            p.unlink(missing_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM darfs WHERE id = ?", (darf_id,))
    return True
