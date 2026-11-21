"""Browser backups use the CLI format and leave no temporary archives behind."""

import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import pjtracker.app as storage
from pjtracker.api.main import app


@pytest.fixture
def backup_paths(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(storage, "DB_PATH", data / "custom.db")
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    original = tempfile.TemporaryDirectory
    monkeypatch.setattr(
        "pjtracker.api.routers.backups.TemporaryDirectory",
        lambda **kwargs: original(dir=downloads, **kwargs),
    )
    return data, downloads


@pytest.mark.skipif(not shutil.which("sqlite3"), reason="backup.sh requires sqlite3 CLI")
def test_backup_download_snapshot_and_restore_format(backup_paths, tmp_path):
    data, downloads = backup_paths
    # Keep WAL open to verify the script takes a snapshot rather than copying the DB file.
    with sqlite3.connect(storage.DB_PATH) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE example (value TEXT)")
        connection.execute("INSERT INTO example VALUES ('saved in WAL')")
        connection.commit()
        (data / "pdfs").mkdir()
        (data / "pdfs" / "invoice.pdf").write_bytes(b"%PDF-example")
        (data / "images").mkdir()
        (data / "images" / "receipt.png").write_bytes(b"image-example")
        (data / ".token").write_text("secret-must-not-be-exported")
        (data / "old-backup.tar.gz").write_bytes(b"old archive")

        response = TestClient(app).post("/api/v1/backups/download")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/gzip"
    assert response.headers["cache-control"] == "no-store"
    assert 'attachment; filename="pjtracker-' in response.headers["content-disposition"]
    assert list(downloads.iterdir()) == []
    with tarfile.open(fileobj=BytesIO(response.content), mode="r:gz") as archive:
        assert set(archive.getnames()) == {
            "pjtracker.db", "pdfs", "pdfs/invoice.pdf", "images", "images/receipt.png",
        }
        assert archive.extractfile("pdfs/invoice.pdf").read() == b"%PDF-example"
        assert archive.extractfile("images/receipt.png").read() == b"image-example"
        snapshot = tmp_path / "snapshot.db"
        snapshot.write_bytes(archive.extractfile("pjtracker.db").read())
    with sqlite3.connect(snapshot) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("SELECT value FROM example").fetchone() == ("saved in WAL",)

    archive_file = tmp_path / "backup.tar.gz"
    archive_file.write_bytes(response.content)
    result = subprocess.run(
        ["bash", str(storage.PROJECT_ROOT / "scripts/restore.sh"), str(archive_file), "--dry-run"],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert not list(data.glob("pjtracker-*.tar.gz"))


@pytest.mark.parametrize("error, status", [
    (subprocess.CalledProcessError(1, "backup.sh", stderr="private failure details"), 500),
    (subprocess.TimeoutExpired("backup.sh", 300), 504),
    (FileNotFoundError("bash missing"), 500),
])
def test_backup_failure_cleans_partial_archive(backup_paths, error, status):
    _, downloads = backup_paths

    def fail(command, **kwargs):
        Path(command[-1]).write_bytes(b"partial archive")
        assert kwargs["env"]["PJTRACKER_DB_PATH"] == str(storage.DB_PATH.resolve())
        raise error

    with patch("pjtracker.api.services.backups.subprocess.run", side_effect=fail):
        response = TestClient(app).post("/api/v1/backups/download")

    assert response.status_code == status
    assert "private failure details" not in response.text
    assert list(downloads.iterdir()) == []
