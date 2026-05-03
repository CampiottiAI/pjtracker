"""Nota Fiscal Tracker – shared DB and helpers (NFs and pages import from here)."""

import hashlib
import re
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

# Repo root: src/pjtracker/app.py -> ../.. = repo root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "pjtracker.db"
PDF_DIR = PROJECT_ROOT / "pdfs"
IMAGES_DIR = PROJECT_ROOT / "images"


def init_db() -> None:
    """Create the nf_entries table if it does not exist and ensure unique (nf_date, verification_code, usd)."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fiscal_months (
                fiscal_mes TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            )
        """)
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
        # Migration: add fiscal_mes (month/year as YYYY-MM)
        try:
            conn.execute("ALTER TABLE nf_entries ADD COLUMN fiscal_mes TEXT")
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
        for statement in (
            "ALTER TABLE boletos ADD COLUMN codigo_barras TEXT",
            "ALTER TABLE boletos ADD COLUMN codigo_barras_digits TEXT",
            "ALTER TABLE boletos ADD COLUMN receipt_value REAL",
            "ALTER TABLE boletos ADD COLUMN receipt_codigo_barras TEXT",
            "ALTER TABLE boletos ADD COLUMN receipt_codigo_barras_digits TEXT",
            "ALTER TABLE boletos ADD COLUMN receipt_match_status TEXT",
        ):
            try:
                conn.execute(statement)
            except sqlite3.OperationalError:
                pass
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_boletos_content_hash
            ON boletos (content_hash) WHERE content_hash IS NOT NULL
        """)
        try:
            conn.execute("ALTER TABLE boletos ADD COLUMN fiscal_mes TEXT")
        except sqlite3.OperationalError:
            pass
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
        for statement in (
            "ALTER TABLE darfs ADD COLUMN codigo_barras TEXT",
            "ALTER TABLE darfs ADD COLUMN codigo_barras_digits TEXT",
            "ALTER TABLE darfs ADD COLUMN receipt_value REAL",
            "ALTER TABLE darfs ADD COLUMN receipt_codigo_barras TEXT",
            "ALTER TABLE darfs ADD COLUMN receipt_codigo_barras_digits TEXT",
            "ALTER TABLE darfs ADD COLUMN receipt_match_status TEXT",
        ):
            try:
                conn.execute(statement)
            except sqlite3.OperationalError:
                pass
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_darfs_content_hash
            ON darfs (content_hash) WHERE content_hash IS NOT NULL
        """)
        try:
            conn.execute("ALTER TABLE darfs ADD COLUMN fiscal_mes TEXT")
        except sqlite3.OperationalError:
            pass
        # IRPJ/CSLL: quarterly tax document PDF + optional receipt image
        conn.execute("""
            CREATE TABLE IF NOT EXISTS irpj_cslls (
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
        try:
            conn.execute("ALTER TABLE irpj_cslls ADD COLUMN content_hash TEXT")
        except sqlite3.OperationalError:
            pass
        for statement in (
            "ALTER TABLE irpj_cslls ADD COLUMN codigo_barras TEXT",
            "ALTER TABLE irpj_cslls ADD COLUMN codigo_barras_digits TEXT",
            "ALTER TABLE irpj_cslls ADD COLUMN receipt_value REAL",
            "ALTER TABLE irpj_cslls ADD COLUMN receipt_codigo_barras TEXT",
            "ALTER TABLE irpj_cslls ADD COLUMN receipt_codigo_barras_digits TEXT",
            "ALTER TABLE irpj_cslls ADD COLUMN receipt_match_status TEXT",
        ):
            try:
                conn.execute(statement)
            except sqlite3.OperationalError:
                pass
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_irpj_cslls_content_hash
            ON irpj_cslls (content_hash) WHERE content_hash IS NOT NULL
        """)
        try:
            conn.execute("ALTER TABLE irpj_cslls ADD COLUMN fiscal_mes TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute(
                "ALTER TABLE irpj_cslls ADD COLUMN attachment_pdf_path TEXT"
            )
        except sqlite3.OperationalError:
            pass
        # Extratos: main statement PDF + optional caixinha PDF
        conn.execute("""
            CREATE TABLE IF NOT EXISTS extratos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                extrato_pdf_path TEXT NOT NULL,
                caixinha_pdf_path TEXT,
                period_start TEXT,
                period_end TEXT,
                saldo_inicial REAL,
                rendimento REAL,
                total_entradas REAL,
                total_saidas REAL,
                saldo_final REAL,
                caixinha_saldo_final REAL,
                extrato_entries_json TEXT,
                caixinha_entries_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                content_hash TEXT
            )
        """)
        for statement in (
            "ALTER TABLE extratos ADD COLUMN caixinha_pdf_path TEXT",
            "ALTER TABLE extratos ADD COLUMN period_start TEXT",
            "ALTER TABLE extratos ADD COLUMN period_end TEXT",
            "ALTER TABLE extratos ADD COLUMN saldo_inicial REAL",
            "ALTER TABLE extratos ADD COLUMN rendimento REAL",
            "ALTER TABLE extratos ADD COLUMN total_entradas REAL",
            "ALTER TABLE extratos ADD COLUMN total_saidas REAL",
            "ALTER TABLE extratos ADD COLUMN saldo_final REAL",
            "ALTER TABLE extratos ADD COLUMN caixinha_saldo_final REAL",
            "ALTER TABLE extratos ADD COLUMN extrato_entries_json TEXT",
            "ALTER TABLE extratos ADD COLUMN caixinha_entries_json TEXT",
            "ALTER TABLE extratos ADD COLUMN updated_at TEXT",
            "ALTER TABLE extratos ADD COLUMN content_hash TEXT",
        ):
            try:
                conn.execute(statement)
            except sqlite3.OperationalError:
                pass
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_extratos_content_hash
            ON extratos (content_hash) WHERE content_hash IS NOT NULL
        """)
        try:
            conn.execute("ALTER TABLE extratos ADD COLUMN fiscal_mes TEXT")
        except sqlite3.OperationalError:
            pass
        for statement in (
            "ALTER TABLE extratos ADD COLUMN higlobe_pdf_path TEXT",
            "ALTER TABLE extratos ADD COLUMN higlobe_entries_json TEXT",
        ):
            try:
                conn.execute(statement)
            except sqlite3.OperationalError:
                pass


def _sanitize_filename(s: str) -> str:
    """Replace characters that are unsafe in filenames."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in s)


# --- Fiscal Mês (month/year) helpers ---

FISCAL_MES_MONTH_NAMES = (
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
)


def format_fiscal_mes(value: str | None) -> str:
    """Format fiscal_mes 'YYYY-MM' for display, e.g. 'Março 2025'. Returns '—' if None or invalid."""
    if not value or not value.strip():
        return "—"
    parts = value.strip().split("-")
    if len(parts) != 2:
        return value
    try:
        year = int(parts[0])
        month = int(parts[1])
        if 1 <= month <= 12:
            return f"{FISCAL_MES_MONTH_NAMES[month - 1]} {year}"
    except ValueError:
        pass
    return value


def fiscal_mes_to_date(fiscal_mes: str | None) -> date | None:
    """Parse fiscal_mes 'YYYY-MM' to first day of that month. Returns None if invalid."""
    if not fiscal_mes or not fiscal_mes.strip():
        return None
    parts = fiscal_mes.strip().split("-")
    if len(parts) != 2:
        return None
    try:
        year = int(parts[0])
        month = int(parts[1])
        if 1 <= month <= 12:
            return date(year, month, 1)
    except ValueError:
        pass
    return None


def default_fiscal_mes_date() -> date:
    """First day of current month, for fiscal month picker default."""
    today = date.today()
    return today.replace(day=1)


def get_explicit_fiscal_months() -> list[str]:
    """Return explicitly created fiscal months, newest first."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "SELECT fiscal_mes FROM fiscal_months ORDER BY fiscal_mes DESC",
        )
        return [str(row[0]) for row in cur.fetchall()]


def save_fiscal_month(fiscal_mes: str) -> bool:
    """Persist an explicit fiscal month. Returns True when inserted, False when it already existed."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO fiscal_months (fiscal_mes, created_at) VALUES (?, ?)",
            (fiscal_mes, datetime.now(timezone.utc).isoformat()),
        )
        return cur.rowcount > 0


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
    fiscal_mes: str | None = None,
) -> tuple[bool, int]:
    """Insert one NF entry; skip if (nf_date, verification_code, usd) already exists.
    Returns (inserted, nf_id): inserted is True if a new row was added, nf_id is the row id in both cases."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO nf_entries (
                company, usd, rate, spread, brl_no_spread, brl_with_spread,
                nf_date, verification_code, payment_via, pdf_path, fiscal_mes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                fiscal_mes,
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
    fiscal_mes: str | None = None,
) -> list[dict]:
    """Return NF entries, optionally filtered by nf_date range and/or fiscal_mes. Newest first. Each row is a dict."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        if fiscal_mes is not None:
            cur = conn.execute(
                "SELECT * FROM nf_entries WHERE fiscal_mes = ? ORDER BY created_at DESC",
                (fiscal_mes,),
            )
        else:
            cur = conn.execute(
                "SELECT * FROM nf_entries ORDER BY created_at DESC",
            )
        rows = [dict(r) for r in cur.fetchall()]

    if date_from is not None or date_to is not None:
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
        rows = filtered
    return rows


def get_nf_by_id(nf_id: int) -> dict | None:
    """Return the NF entry row for the given id, or None if not found."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM nf_entries WHERE id = ?", (nf_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def delete_nf(nf_id: int) -> bool:
    """Delete NF row, its PDF, and all nf_images. Returns True if deleted, False if not found."""
    row = get_nf_by_id(nf_id)
    if not row:
        return False
    project_root = Path(DB_PATH).resolve().parent
    # Delete image files and nf_images rows
    for img in get_nf_images(nf_id):
        raw = img.get("image_path")
        if raw and str(raw).strip():
            p = Path(raw)
            if not p.is_absolute():
                p = project_root / raw
            if p.exists():
                p.unlink(missing_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM nf_images WHERE nf_id = ?", (nf_id,))
    # Delete PDF file
    pdf_path_raw = row.get("pdf_path")
    if pdf_path_raw and str(pdf_path_raw).strip():
        p = Path(pdf_path_raw)
        if not p.is_absolute():
            p = project_root / pdf_path_raw
        if p.exists():
            p.unlink(missing_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM nf_entries WHERE id = ?", (nf_id,))
    return True


def update_nf_fiscal_mes(nf_id: int, fiscal_mes: str | None) -> None:
    """Update fiscal_mes for an NF entry."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE nf_entries SET fiscal_mes = ? WHERE id = ?",
            (fiscal_mes, nf_id),
        )


def update_nf_pdf(
    nf_id: int,
    pdf_bytes: bytes,
    *,
    company: str | None,
    usd: float,
    rate: float,
    spread: float,
    brl_no_spread: float,
    brl_with_spread: float,
    nf_date: str | None,
    verification_code: str | None,
    payment_via: str | None,
) -> bool:
    """Replace NF PDF and update parsed fields. Returns False if NF not found."""
    row = get_nf_by_id(nf_id)
    if not row:
        return False
    project_root_dir = Path(DB_PATH).resolve().parent
    old_path = row.get("pdf_path")
    if old_path:
        full_old = Path(old_path) if Path(old_path).is_absolute() else project_root_dir / old_path
        if full_old.exists():
            full_old.unlink(missing_ok=True)
    new_path = save_pdf(pdf_bytes, verification_code or "-", nf_date, usd)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE nf_entries
            SET company = ?, usd = ?, rate = ?, spread = ?,
                brl_no_spread = ?, brl_with_spread = ?,
                nf_date = ?, verification_code = ?, payment_via = ?,
                pdf_path = ?
            WHERE id = ?
            """,
            (
                company, usd, rate, spread,
                brl_no_spread, brl_with_spread,
                nf_date, verification_code, payment_via,
                str(new_path), nf_id,
            ),
        )
    return True


def delete_nf_image(nf_id: int, image_id: int) -> bool:
    """Delete a single NF image row and its file. Returns True if deleted."""
    project_root_dir = Path(DB_PATH).resolve().parent
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT * FROM nf_images WHERE id = ? AND nf_id = ?", (image_id, nf_id)
        )
        row = cur.fetchone()
        if not row:
            return False
        raw = row["image_path"]
        if raw and str(raw).strip():
            p = Path(raw)
            if not p.is_absolute():
                p = project_root_dir / raw
            if p.exists():
                p.unlink(missing_ok=True)
        conn.execute("DELETE FROM nf_images WHERE id = ?", (image_id,))
    return True


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
    codigo_barras: str | None = None,
    codigo_barras_digits: str | None = None,
    receipt_path: str | None = None,
    receipt_date: str | None = None,
    receipt_value: float | None = None,
    receipt_codigo_barras: str | None = None,
    receipt_codigo_barras_digits: str | None = None,
    receipt_match_status: str | None = None,
    fiscal_mes: str | None = None,
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
                    codigo_barras, codigo_barras_digits, receipt_date, receipt_value,
                    receipt_codigo_barras, receipt_codigo_barras_digits, receipt_match_status,
                    created_at, updated_at, content_hash, fiscal_mes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pdf_path,
                    receipt_path,
                    value,
                    emission_date,
                    deadline_date,
                    codigo_barras,
                    codigo_barras_digits,
                    receipt_date,
                    receipt_value,
                    receipt_codigo_barras,
                    receipt_codigo_barras_digits,
                    receipt_match_status,
                    now,
                    now,
                    content_hash,
                    fiscal_mes,
                ),
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


def get_boletos(fiscal_mes: str | None = None) -> list[dict]:
    """Return all boletos, optionally filtered by fiscal_mes. Newest first."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        if fiscal_mes is not None:
            cur = conn.execute(
                "SELECT * FROM boletos WHERE fiscal_mes = ? ORDER BY created_at DESC",
                (fiscal_mes,),
            )
        else:
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


def _compute_receipt_match_status(
    document_digits: str | None,
    receipt_digits: str | None,
) -> str | None:
    if not document_digits or not receipt_digits:
        return None
    return "match" if document_digits == receipt_digits else "mismatch"


def update_boleto_fields(
    boleto_id: int,
    *,
    value: float | None,
    emission_date: str | None,
    deadline_date: str | None,
    codigo_barras: str | None,
    codigo_barras_digits: str | None,
    receipt_date: str | None,
    receipt_value: float | None,
    receipt_codigo_barras: str | None,
    receipt_codigo_barras_digits: str | None,
    fiscal_mes: str | None,
) -> bool:
    """Update editable boleto fields and derived hashes/match status."""
    row = get_boleto_by_id(boleto_id)
    if not row:
        return False
    content_hash = compute_boleto_content_hash(value, emission_date, deadline_date)
    receipt_match_status = _compute_receipt_match_status(
        codigo_barras_digits,
        receipt_codigo_barras_digits,
    )
    now = datetime.now(timezone.utc).isoformat()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                UPDATE boletos
                SET value = ?, emission_date = ?, deadline_date = ?,
                    codigo_barras = ?, codigo_barras_digits = ?,
                    receipt_date = ?, receipt_value = ?,
                    receipt_codigo_barras = ?, receipt_codigo_barras_digits = ?,
                    receipt_match_status = ?, fiscal_mes = ?, content_hash = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    value,
                    emission_date,
                    deadline_date,
                    codigo_barras,
                    codigo_barras_digits,
                    receipt_date,
                    receipt_value,
                    receipt_codigo_barras,
                    receipt_codigo_barras_digits,
                    receipt_match_status,
                    fiscal_mes,
                    content_hash,
                    now,
                    boleto_id,
                ),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def update_boleto_pdf(
    boleto_id: int,
    pdf_bytes: bytes,
    value: float | None,
    emission_date: str | None,
    deadline_date: str | None,
    codigo_barras: str | None,
    codigo_barras_digits: str | None,
    receipt_match_status: str | None,
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
                UPDATE boletos
                SET pdf_path = ?, value = ?, emission_date = ?, deadline_date = ?,
                    codigo_barras = ?, codigo_barras_digits = ?, receipt_match_status = ?,
                    content_hash = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    path_str,
                    value,
                    emission_date,
                    deadline_date,
                    codigo_barras,
                    codigo_barras_digits,
                    receipt_match_status,
                    content_hash,
                    now,
                    boleto_id,
                ),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def update_boleto_receipt(
    boleto_id: int,
    receipt_path: str,
    receipt_date: str | None,
    receipt_value: float | None = None,
    receipt_codigo_barras: str | None = None,
    receipt_codigo_barras_digits: str | None = None,
    receipt_match_status: str | None = None,
) -> None:
    """Set receipt path and date for a boleto."""
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE boletos
            SET receipt_path = ?, receipt_date = ?, receipt_value = ?,
                receipt_codigo_barras = ?, receipt_codigo_barras_digits = ?,
                receipt_match_status = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                receipt_path,
                receipt_date,
                receipt_value,
                receipt_codigo_barras,
                receipt_codigo_barras_digits,
                receipt_match_status,
                now,
                boleto_id,
            ),
        )


def update_boleto_fiscal_mes(boleto_id: int, fiscal_mes: str | None) -> None:
    """Update fiscal_mes for a boleto."""
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE boletos SET fiscal_mes = ?, updated_at = ? WHERE id = ?",
            (fiscal_mes, now, boleto_id),
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
    codigo_barras: str | None = None,
    codigo_barras_digits: str | None = None,
    receipt_path: str | None = None,
    receipt_date: str | None = None,
    receipt_value: float | None = None,
    receipt_codigo_barras: str | None = None,
    receipt_codigo_barras_digits: str | None = None,
    receipt_match_status: str | None = None,
    fiscal_mes: str | None = None,
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
                    codigo_barras, codigo_barras_digits, receipt_date, receipt_value,
                    receipt_codigo_barras, receipt_codigo_barras_digits, receipt_match_status,
                    created_at, updated_at, content_hash, fiscal_mes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pdf_path,
                    receipt_path,
                    value,
                    emission_date,
                    deadline_date,
                    codigo_barras,
                    codigo_barras_digits,
                    receipt_date,
                    receipt_value,
                    receipt_codigo_barras,
                    receipt_codigo_barras_digits,
                    receipt_match_status,
                    now,
                    now,
                    content_hash,
                    fiscal_mes,
                ),
            )
            return (True, cur.lastrowid)
    except sqlite3.IntegrityError:
        return (False, None)


def get_darfs(fiscal_mes: str | None = None) -> list[dict]:
    """Return all DARFs, optionally filtered by fiscal_mes. Newest first."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        if fiscal_mes is not None:
            cur = conn.execute(
                "SELECT * FROM darfs WHERE fiscal_mes = ? ORDER BY created_at DESC",
                (fiscal_mes,),
            )
        else:
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


def update_darf_fields(
    darf_id: int,
    *,
    value: float | None,
    emission_date: str | None,
    deadline_date: str | None,
    codigo_barras: str | None,
    codigo_barras_digits: str | None,
    receipt_date: str | None,
    receipt_value: float | None,
    receipt_codigo_barras: str | None,
    receipt_codigo_barras_digits: str | None,
    fiscal_mes: str | None,
) -> bool:
    """Update editable DARF fields and derived hashes/match status."""
    row = get_darf_by_id(darf_id)
    if not row:
        return False
    content_hash = compute_darf_content_hash(value, emission_date, deadline_date)
    receipt_match_status = _compute_receipt_match_status(
        codigo_barras_digits,
        receipt_codigo_barras_digits,
    )
    now = datetime.now(timezone.utc).isoformat()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                UPDATE darfs
                SET value = ?, emission_date = ?, deadline_date = ?,
                    codigo_barras = ?, codigo_barras_digits = ?,
                    receipt_date = ?, receipt_value = ?,
                    receipt_codigo_barras = ?, receipt_codigo_barras_digits = ?,
                    receipt_match_status = ?, fiscal_mes = ?, content_hash = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    value,
                    emission_date,
                    deadline_date,
                    codigo_barras,
                    codigo_barras_digits,
                    receipt_date,
                    receipt_value,
                    receipt_codigo_barras,
                    receipt_codigo_barras_digits,
                    receipt_match_status,
                    fiscal_mes,
                    content_hash,
                    now,
                    darf_id,
                ),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def update_darf_pdf(
    darf_id: int,
    pdf_bytes: bytes,
    value: float | None,
    emission_date: str | None,
    deadline_date: str | None,
    codigo_barras: str | None,
    codigo_barras_digits: str | None,
    receipt_match_status: str | None,
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
                UPDATE darfs
                SET pdf_path = ?, value = ?, emission_date = ?, deadline_date = ?,
                    codigo_barras = ?, codigo_barras_digits = ?, receipt_match_status = ?,
                    content_hash = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    path_str,
                    value,
                    emission_date,
                    deadline_date,
                    codigo_barras,
                    codigo_barras_digits,
                    receipt_match_status,
                    content_hash,
                    now,
                    darf_id,
                ),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def update_darf_receipt(
    darf_id: int,
    receipt_path: str,
    receipt_date: str | None,
    receipt_value: float | None = None,
    receipt_codigo_barras: str | None = None,
    receipt_codigo_barras_digits: str | None = None,
    receipt_match_status: str | None = None,
) -> None:
    """Set receipt path and date for a DARF."""
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE darfs
            SET receipt_path = ?, receipt_date = ?, receipt_value = ?,
                receipt_codigo_barras = ?, receipt_codigo_barras_digits = ?,
                receipt_match_status = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                receipt_path,
                receipt_date,
                receipt_value,
                receipt_codigo_barras,
                receipt_codigo_barras_digits,
                receipt_match_status,
                now,
                darf_id,
            ),
        )


def update_darf_fiscal_mes(darf_id: int, fiscal_mes: str | None) -> None:
    """Update fiscal_mes for a DARF."""
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE darfs SET fiscal_mes = ?, updated_at = ? WHERE id = ?",
            (fiscal_mes, now, darf_id),
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


# --- IRPJ/CSLL ---


def compute_irpj_csll_content_hash(
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


def save_irpj_csll_pdf(
    pdf_bytes: bytes, emission_date: str | None = None, value: float | None = None
) -> Path:
    """Save IRPJ/CSLL PDF to pdfs/ with unique name. Returns path."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    safe_date = _sanitize_filename((emission_date or "").replace("/", "-"))[:20] or "nodate"
    val_part = f"{value:.2f}" if value is not None else "0"
    base = f"irpj_csll_{safe_date}_{val_part}"
    path = PDF_DIR / f"{base}.pdf"
    counter = 0
    while path.exists():
        counter += 1
        path = PDF_DIR / f"{base}_{counter}.pdf"
    path.write_bytes(pdf_bytes)
    return path


def save_irpj_csll_attachment_pdf(irpj_csll_id: int, pdf_bytes: bytes) -> Path:
    """Save supplementary IRPJ/CSLL PDF (no parsing). Returns path under PDF_DIR."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    base = f"irpj_csll_attachment_{irpj_csll_id}_{ts}"
    path = PDF_DIR / f"{base}.pdf"
    counter = 0
    while path.exists():
        counter += 1
        path = PDF_DIR / f"{base}_{counter}.pdf"
    path.write_bytes(pdf_bytes)
    return path


def save_irpj_csll_receipt(irpj_csll_id: int, image_bytes: bytes, mime_or_ext: str) -> Path:
    """Save receipt image for an IRPJ/CSLL document. Returns path."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    ext = mime_or_ext.strip().lower()
    if "/" in ext:
        ext = ext.split("/", 1)[-1]
    if ext not in ("png", "jpg", "jpeg", "gif", "webp"):
        ext = "png"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    base = f"irpj_csll_receipt_{irpj_csll_id}_{ts}"
    path = IMAGES_DIR / f"{base}.{ext}"
    counter = 0
    while path.exists():
        counter += 1
        path = IMAGES_DIR / f"{base}_{counter}.{ext}"
    path.write_bytes(image_bytes)
    return path


def save_irpj_csll_entry(
    pdf_path: str,
    value: float | None = None,
    emission_date: str | None = None,
    deadline_date: str | None = None,
    codigo_barras: str | None = None,
    codigo_barras_digits: str | None = None,
    receipt_path: str | None = None,
    receipt_date: str | None = None,
    receipt_value: float | None = None,
    receipt_codigo_barras: str | None = None,
    receipt_codigo_barras_digits: str | None = None,
    receipt_match_status: str | None = None,
    fiscal_mes: str | None = None,
) -> tuple[bool, int | None]:
    """Insert one IRPJ/CSLL row. Returns (inserted, id) or (False, None) on duplicate."""
    content_hash = compute_irpj_csll_content_hash(value, emission_date, deadline_date)
    now = datetime.now(timezone.utc).isoformat()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute(
                """
                INSERT INTO irpj_cslls (
                    pdf_path, receipt_path, value, emission_date, deadline_date,
                    codigo_barras, codigo_barras_digits, receipt_date, receipt_value,
                    receipt_codigo_barras, receipt_codigo_barras_digits, receipt_match_status,
                    created_at, updated_at, content_hash, fiscal_mes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pdf_path,
                    receipt_path,
                    value,
                    emission_date,
                    deadline_date,
                    codigo_barras,
                    codigo_barras_digits,
                    receipt_date,
                    receipt_value,
                    receipt_codigo_barras,
                    receipt_codigo_barras_digits,
                    receipt_match_status,
                    now,
                    now,
                    content_hash,
                    fiscal_mes,
                ),
            )
            return (True, cur.lastrowid)
    except sqlite3.IntegrityError:
        return (False, None)


def get_irpj_cslls(fiscal_mes: str | None = None) -> list[dict]:
    """Return all IRPJ/CSLL rows, optionally filtered by fiscal_mes. Newest first."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        if fiscal_mes is not None:
            cur = conn.execute(
                "SELECT * FROM irpj_cslls WHERE fiscal_mes = ? ORDER BY created_at DESC",
                (fiscal_mes,),
            )
        else:
            cur = conn.execute(
                "SELECT * FROM irpj_cslls ORDER BY created_at DESC",
            )
        return [dict(r) for r in cur.fetchall()]


def get_irpj_csll_by_id(irpj_csll_id: int) -> dict | None:
    """Return one IRPJ/CSLL row by id or None."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM irpj_cslls WHERE id = ?", (irpj_csll_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def update_irpj_csll_fields(
    irpj_csll_id: int,
    *,
    value: float | None,
    emission_date: str | None,
    deadline_date: str | None,
    codigo_barras: str | None,
    codigo_barras_digits: str | None,
    receipt_date: str | None,
    receipt_value: float | None,
    receipt_codigo_barras: str | None,
    receipt_codigo_barras_digits: str | None,
    fiscal_mes: str | None,
) -> bool:
    """Update editable IRPJ/CSLL fields and derived hashes/match status."""
    row = get_irpj_csll_by_id(irpj_csll_id)
    if not row:
        return False
    content_hash = compute_irpj_csll_content_hash(value, emission_date, deadline_date)
    receipt_match_status = _compute_receipt_match_status(
        codigo_barras_digits,
        receipt_codigo_barras_digits,
    )
    now = datetime.now(timezone.utc).isoformat()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                UPDATE irpj_cslls
                SET value = ?, emission_date = ?, deadline_date = ?,
                    codigo_barras = ?, codigo_barras_digits = ?,
                    receipt_date = ?, receipt_value = ?,
                    receipt_codigo_barras = ?, receipt_codigo_barras_digits = ?,
                    receipt_match_status = ?, fiscal_mes = ?, content_hash = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    value,
                    emission_date,
                    deadline_date,
                    codigo_barras,
                    codigo_barras_digits,
                    receipt_date,
                    receipt_value,
                    receipt_codigo_barras,
                    receipt_codigo_barras_digits,
                    receipt_match_status,
                    fiscal_mes,
                    content_hash,
                    now,
                    irpj_csll_id,
                ),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def update_irpj_csll_pdf(
    irpj_csll_id: int,
    pdf_bytes: bytes,
    value: float | None,
    emission_date: str | None,
    deadline_date: str | None,
    codigo_barras: str | None,
    codigo_barras_digits: str | None,
    receipt_match_status: str | None,
) -> bool:
    """Replace IRPJ/CSLL PDF and update parsed fields. Keeps receipt_path/receipt_date unchanged."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    row = get_irpj_csll_by_id(irpj_csll_id)
    if not row:
        return False
    old_path = row.get("pdf_path")
    if old_path:
        full_old = Path(DB_PATH).resolve().parent / old_path if not Path(old_path).is_absolute() else Path(old_path)
        if full_old.exists():
            full_old.unlink(missing_ok=True)
    new_path = save_irpj_csll_pdf(pdf_bytes, emission_date, value)
    path_str = str(new_path)
    content_hash = compute_irpj_csll_content_hash(value, emission_date, deadline_date)
    now = datetime.now(timezone.utc).isoformat()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                UPDATE irpj_cslls
                SET pdf_path = ?, value = ?, emission_date = ?, deadline_date = ?,
                    codigo_barras = ?, codigo_barras_digits = ?, receipt_match_status = ?,
                    content_hash = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    path_str,
                    value,
                    emission_date,
                    deadline_date,
                    codigo_barras,
                    codigo_barras_digits,
                    receipt_match_status,
                    content_hash,
                    now,
                    irpj_csll_id,
                ),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def set_irpj_csll_attachment_pdf_path(irpj_csll_id: int, attachment_pdf_path: str | None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE irpj_cslls SET attachment_pdf_path = ?, updated_at = ?
            WHERE id = ?
            """,
            (attachment_pdf_path, now, irpj_csll_id),
        )


def replace_irpj_csll_attachment_pdf(irpj_csll_id: int, pdf_bytes: bytes) -> bool:
    """Replace supplementary PDF; removes previous file if present."""
    row = get_irpj_csll_by_id(irpj_csll_id)
    if not row:
        return False
    project_root_path = Path(DB_PATH).resolve().parent
    old_raw = row.get("attachment_pdf_path")
    if old_raw:
        old_p = Path(old_raw) if Path(old_raw).is_absolute() else project_root_path / old_raw
        if old_p.exists():
            old_p.unlink(missing_ok=True)
    apath = save_irpj_csll_attachment_pdf(irpj_csll_id, pdf_bytes)
    set_irpj_csll_attachment_pdf_path(irpj_csll_id, str(apath))
    return True


def clear_irpj_csll_attachment_pdf(irpj_csll_id: int) -> bool:
    """Remove supplementary PDF file and clear path. Returns False if row missing."""
    row = get_irpj_csll_by_id(irpj_csll_id)
    if not row:
        return False
    project_root_path = Path(DB_PATH).resolve().parent
    old_raw = row.get("attachment_pdf_path")
    if old_raw:
        old_p = Path(old_raw) if Path(old_raw).is_absolute() else project_root_path / old_raw
        if old_p.exists():
            old_p.unlink(missing_ok=True)
    set_irpj_csll_attachment_pdf_path(irpj_csll_id, None)
    return True


def update_irpj_csll_receipt(
    irpj_csll_id: int,
    receipt_path: str,
    receipt_date: str | None,
    receipt_value: float | None = None,
    receipt_codigo_barras: str | None = None,
    receipt_codigo_barras_digits: str | None = None,
    receipt_match_status: str | None = None,
) -> None:
    """Set receipt path and date for an IRPJ/CSLL document."""
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE irpj_cslls
            SET receipt_path = ?, receipt_date = ?, receipt_value = ?,
                receipt_codigo_barras = ?, receipt_codigo_barras_digits = ?,
                receipt_match_status = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                receipt_path,
                receipt_date,
                receipt_value,
                receipt_codigo_barras,
                receipt_codigo_barras_digits,
                receipt_match_status,
                now,
                irpj_csll_id,
            ),
        )


def update_irpj_csll_fiscal_mes(irpj_csll_id: int, fiscal_mes: str | None) -> None:
    """Update fiscal_mes for an IRPJ/CSLL document."""
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE irpj_cslls SET fiscal_mes = ?, updated_at = ? WHERE id = ?",
            (fiscal_mes, now, irpj_csll_id),
        )


def delete_irpj_csll(irpj_csll_id: int) -> bool:
    """Delete IRPJ/CSLL row and its PDF and receipt files. Returns True if deleted, False if not found."""
    row = get_irpj_csll_by_id(irpj_csll_id)
    if not row:
        return False
    project_root = Path(DB_PATH).resolve().parent
    for path_key in ("pdf_path", "receipt_path", "attachment_pdf_path"):
        raw = row.get(path_key)
        if not raw or (isinstance(raw, str) and not raw.strip()):
            continue
        p = Path(raw)
        if not p.is_absolute():
            p = project_root / raw
        if p.exists():
            p.unlink(missing_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM irpj_cslls WHERE id = ?", (irpj_csll_id,))
    return True


# --- Extratos ---


def compute_extrato_content_hash(
    period_start: str | None,
    period_end: str | None,
) -> str | None:
    """Deterministic hash from the statement period."""
    start = (period_start or "").strip()
    end = (period_end or "").strip()
    payload = f"{start}|{end}"
    if payload == "|":
        return None
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def save_extrato_pdf(
    pdf_bytes: bytes,
    period_start: str | None = None,
    period_end: str | None = None,
) -> Path:
    """Save extrato PDF to pdfs/ with a unique name. Returns path."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    safe_start = _sanitize_filename((period_start or "").replace("/", "-"))[:20] or "nodate"
    safe_end = _sanitize_filename((period_end or "").replace("/", "-"))[:20] or "nodate"
    base = f"extrato_{safe_start}_{safe_end}"
    path = PDF_DIR / f"{base}.pdf"
    counter = 0
    while path.exists():
        counter += 1
        path = PDF_DIR / f"{base}_{counter}.pdf"
    path.write_bytes(pdf_bytes)
    return path


def save_caixinha_pdf(
    pdf_bytes: bytes,
    period_start: str | None = None,
    period_end: str | None = None,
) -> Path:
    """Save caixinha PDF to pdfs/ with a unique name. Returns path."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    safe_start = _sanitize_filename((period_start or "").replace("/", "-"))[:20] or "nodate"
    safe_end = _sanitize_filename((period_end or "").replace("/", "-"))[:20] or "nodate"
    base = f"caixinha_{safe_start}_{safe_end}"
    path = PDF_DIR / f"{base}.pdf"
    counter = 0
    while path.exists():
        counter += 1
        path = PDF_DIR / f"{base}_{counter}.pdf"
    path.write_bytes(pdf_bytes)
    return path


def save_higlobe_pdf(
    pdf_bytes: bytes,
    period_start: str | None = None,
    period_end: str | None = None,
) -> Path:
    """Save Higlobe statement PDF to pdfs/ with a unique name. Returns path."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    safe_start = _sanitize_filename((period_start or "").replace("/", "-"))[:20] or "nodate"
    safe_end = _sanitize_filename((period_end or "").replace("/", "-"))[:20] or "nodate"
    base = f"higlobe_{safe_start}_{safe_end}"
    path = PDF_DIR / f"{base}.pdf"
    counter = 0
    while path.exists():
        counter += 1
        path = PDF_DIR / f"{base}_{counter}.pdf"
    path.write_bytes(pdf_bytes)
    return path


def save_extrato_entry(
    *,
    extrato_pdf_path: str,
    period_start: str | None = None,
    period_end: str | None = None,
    saldo_inicial: float | None = None,
    rendimento: float | None = None,
    total_entradas: float | None = None,
    total_saidas: float | None = None,
    saldo_final: float | None = None,
    extrato_entries_json: str | None = None,
    caixinha_pdf_path: str | None = None,
    caixinha_saldo_final: float | None = None,
    caixinha_entries_json: str | None = None,
    higlobe_pdf_path: str | None = None,
    higlobe_entries_json: str | None = None,
    fiscal_mes: str | None = None,
) -> tuple[bool, int | None]:
    """Insert one extrato row. Returns (inserted, id)."""
    content_hash = compute_extrato_content_hash(period_start, period_end)
    now = datetime.now(timezone.utc).isoformat()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute(
                """
                INSERT INTO extratos (
                    extrato_pdf_path, caixinha_pdf_path, period_start, period_end,
                    saldo_inicial, rendimento, total_entradas, total_saidas, saldo_final,
                    caixinha_saldo_final, extrato_entries_json, caixinha_entries_json,
                    higlobe_pdf_path, higlobe_entries_json,
                    created_at, updated_at, content_hash, fiscal_mes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    extrato_pdf_path,
                    caixinha_pdf_path,
                    period_start,
                    period_end,
                    saldo_inicial,
                    rendimento,
                    total_entradas,
                    total_saidas,
                    saldo_final,
                    caixinha_saldo_final,
                    extrato_entries_json,
                    caixinha_entries_json,
                    higlobe_pdf_path,
                    higlobe_entries_json,
                    now,
                    now,
                    content_hash,
                    fiscal_mes,
                ),
            )
            return (True, cur.lastrowid)
    except sqlite3.IntegrityError:
        return (False, None)


def get_extratos(fiscal_mes: str | None = None) -> list[dict]:
    """Return all extratos, optionally filtered by fiscal_mes. Newest first."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        if fiscal_mes is not None:
            cur = conn.execute(
                "SELECT * FROM extratos WHERE fiscal_mes = ? ORDER BY created_at DESC",
                (fiscal_mes,),
            )
        else:
            cur = conn.execute("SELECT * FROM extratos ORDER BY created_at DESC")
        return [dict(r) for r in cur.fetchall()]


def get_extrato_by_id(extrato_id: int) -> dict | None:
    """Return one extrato by id or None."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM extratos WHERE id = ?", (extrato_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def update_extrato_pdf(
    extrato_id: int,
    pdf_bytes: bytes,
    *,
    period_start: str | None,
    period_end: str | None,
    saldo_inicial: float | None,
    rendimento: float | None,
    total_entradas: float | None,
    total_saidas: float | None,
    saldo_final: float | None,
    extrato_entries_json: str | None,
) -> bool:
    """Replace the main extrato PDF and update parsed fields."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    row = get_extrato_by_id(extrato_id)
    if not row:
        return False
    old_path = row.get("extrato_pdf_path")
    if old_path:
        full_old = Path(DB_PATH).resolve().parent / old_path if not Path(old_path).is_absolute() else Path(old_path)
        if full_old.exists():
            full_old.unlink(missing_ok=True)
    new_path = save_extrato_pdf(pdf_bytes, period_start, period_end)
    content_hash = compute_extrato_content_hash(period_start, period_end)
    now = datetime.now(timezone.utc).isoformat()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                UPDATE extratos
                SET extrato_pdf_path = ?, period_start = ?, period_end = ?,
                    saldo_inicial = ?, rendimento = ?, total_entradas = ?,
                    total_saidas = ?, saldo_final = ?, extrato_entries_json = ?,
                    content_hash = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    str(new_path),
                    period_start,
                    period_end,
                    saldo_inicial,
                    rendimento,
                    total_entradas,
                    total_saidas,
                    saldo_final,
                    extrato_entries_json,
                    content_hash,
                    now,
                    extrato_id,
                ),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def update_caixinha_pdf(
    extrato_id: int,
    pdf_bytes: bytes,
    *,
    period_start: str | None,
    period_end: str | None,
    caixinha_saldo_final: float | None,
    caixinha_entries_json: str | None,
) -> bool:
    """Replace the caixinha PDF and update parsed fields."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    row = get_extrato_by_id(extrato_id)
    if not row:
        return False
    old_path = row.get("caixinha_pdf_path")
    if old_path:
        full_old = Path(DB_PATH).resolve().parent / old_path if not Path(old_path).is_absolute() else Path(old_path)
        if full_old.exists():
            full_old.unlink(missing_ok=True)
    new_path = save_caixinha_pdf(pdf_bytes, period_start, period_end)
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE extratos
            SET caixinha_pdf_path = ?, caixinha_saldo_final = ?,
                caixinha_entries_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                str(new_path),
                caixinha_saldo_final,
                caixinha_entries_json,
                now,
                extrato_id,
            ),
        )
    return True


def update_higlobe_pdf(
    extrato_id: int,
    pdf_bytes: bytes,
    *,
    period_start: str | None,
    period_end: str | None,
    higlobe_entries_json: str | None,
) -> bool:
    """Replace the Higlobe PDF and update parsed fields."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    row = get_extrato_by_id(extrato_id)
    if not row:
        return False
    old_path = row.get("higlobe_pdf_path")
    if old_path:
        full_old = Path(DB_PATH).resolve().parent / old_path if not Path(old_path).is_absolute() else Path(old_path)
        if full_old.exists():
            full_old.unlink(missing_ok=True)
    new_path = save_higlobe_pdf(pdf_bytes, period_start, period_end)
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE extratos
            SET higlobe_pdf_path = ?, higlobe_entries_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                str(new_path),
                higlobe_entries_json,
                now,
                extrato_id,
            ),
        )
    return True


def remove_higlobe_pdf(extrato_id: int) -> bool:
    """Delete the stored Higlobe PDF and clear its parsed fields."""
    row = get_extrato_by_id(extrato_id)
    if not row:
        return False
    old_path = row.get("higlobe_pdf_path")
    if old_path:
        full_old = Path(DB_PATH).resolve().parent / old_path if not Path(old_path).is_absolute() else Path(old_path)
        if full_old.exists():
            full_old.unlink(missing_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE extratos
            SET higlobe_pdf_path = NULL, higlobe_entries_json = NULL, updated_at = ?
            WHERE id = ?
            """,
            (now, extrato_id),
        )
    return True


def remove_caixinha_pdf(extrato_id: int) -> bool:
    """Delete the stored caixinha PDF and clear its parsed fields."""
    row = get_extrato_by_id(extrato_id)
    if not row:
        return False
    old_path = row.get("caixinha_pdf_path")
    if old_path:
        full_old = Path(DB_PATH).resolve().parent / old_path if not Path(old_path).is_absolute() else Path(old_path)
        if full_old.exists():
            full_old.unlink(missing_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE extratos
            SET caixinha_pdf_path = NULL, caixinha_saldo_final = NULL,
                caixinha_entries_json = NULL, updated_at = ?
            WHERE id = ?
            """,
            (now, extrato_id),
        )
    return True


def update_extrato_fiscal_mes(extrato_id: int, fiscal_mes: str | None) -> None:
    """Update fiscal_mes for an extrato."""
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE extratos SET fiscal_mes = ?, updated_at = ? WHERE id = ?",
            (fiscal_mes, now, extrato_id),
        )


def delete_extrato(extrato_id: int) -> bool:
    """Delete extrato row and its PDFs. Returns True if deleted, False if not found."""
    row = get_extrato_by_id(extrato_id)
    if not row:
        return False
    project_root = Path(DB_PATH).resolve().parent
    for path_key in ("extrato_pdf_path", "caixinha_pdf_path", "higlobe_pdf_path"):
        raw = row.get(path_key)
        if not raw or (isinstance(raw, str) and not raw.strip()):
            continue
        p = Path(raw)
        if not p.is_absolute():
            p = project_root / raw
        if p.exists():
            p.unlink(missing_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM extratos WHERE id = ?", (extrato_id,))
    return True
