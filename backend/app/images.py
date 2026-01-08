# app/images.py
from pathlib import Path
from datetime import date
from uuid import uuid4
from fastapi import UploadFile

BASE_DIR = Path(__file__).resolve().parent.parent  # jeśli images.py jest w app/
MEDIA_ROOT = BASE_DIR / "media"                    # musi pasować do main.py

async def save_upload_file(upload_file: UploadFile, media_dir: str = "media"):
    """
    media_dir: np. "media/tpm" albo "media/book"
    zapis: <media_dir>/<YYYY>/<MM>/<DD>/<uuid>.<ext>
    url:   /media/<ścieżka_względem MEDIA_ROOT>
    """
    today = date.today()
    rel_date = Path(str(today.year)) / f"{today.month:02d}" / f"{today.day:02d}"

    # media_dir może być "media/tpm" -> zrób z tego ścieżkę absolutną
    target_dir = (BASE_DIR / media_dir) / rel_date
    target_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(upload_file.filename or "").suffix or ".bin"
    filename = f"{uuid4().hex}{ext}"
    file_path = target_dir / filename

    content = await upload_file.read()
    file_path.write_bytes(content)

    # url ma być względem MEDIA_ROOT
    rel_to_media = file_path.relative_to(MEDIA_ROOT).as_posix()
    public_url = f"/media/{rel_to_media}"

    return str(file_path), public_url
