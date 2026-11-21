"""Download an on-demand backup without retaining an archive on the host."""

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from pjtracker.api.services.backups import BackupError, BackupTimeout, create_backup

router = APIRouter(prefix="/backups", tags=["backups"])


@router.post("/download", response_class=FileResponse)
def download_backup():
    directory = TemporaryDirectory(prefix="pjtracker-download-")
    try:
        archive = create_backup(Path(directory.name))
        return FileResponse(
            archive,
            media_type="application/gzip",
            filename=archive.name,
            headers={"Cache-Control": "no-store"},
            background=BackgroundTask(directory.cleanup),
        )
    except Exception as exc:
        directory.cleanup()
        if isinstance(exc, BackupTimeout):
            raise HTTPException(504, "O backup demorou demais. Tente novamente.") from exc
        if isinstance(exc, BackupError):
            raise HTTPException(500, "Não foi possível gerar o backup. Consulte os logs do servidor.") from exc
        raise
