"""Create browser downloads using the same archive format as the backup CLI."""

from __future__ import annotations

import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path

import pjtracker.app as storage

logger = logging.getLogger(__name__)


class BackupError(Exception):
    """A backup could not be completed."""


class BackupTimeout(BackupError):
    """The backup took too long."""


def create_backup(directory: Path) -> Path:
    archive = directory / f"pjtracker-{datetime.now():%Y%m%d-%H%M%S}.tar.gz"
    try:
        subprocess.run(
            [
                "bash",
                str(storage.PROJECT_ROOT / "scripts" / "backup.sh"),
                "--local-only",
                "--output",
                str(archive),
            ],
            env={
                **os.environ,
                "PJTRACKER_DB_PATH": str(Path(storage.DB_PATH).resolve()),
                "TMPDIR": str(directory),
            },
            capture_output=True,
            text=True,
            check=True,
            timeout=300,
        )
        if not archive.is_file():
            raise BackupError("Backup script did not create an archive")
    except subprocess.TimeoutExpired as exc:
        raise BackupTimeout("Backup exceeded five minutes") from exc
    except subprocess.CalledProcessError as exc:
        logger.error("Backup script failed: %s", exc.stderr)
        raise BackupError("Backup script failed") from exc
    except OSError as exc:
        logger.exception("Could not run backup script")
        raise BackupError("Could not run backup script") from exc
    return archive
