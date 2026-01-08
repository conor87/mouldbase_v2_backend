# app/images.py
import os
from uuid import uuid4
from datetime import datetime
from fastapi import UploadFile, HTTPException, status

MEDIA_DIR = "media"
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}
ALLOWED_CONTENT_PREFIX = "image/"
MAX_SIZE_MB = 205
MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024

os.makedirs(MEDIA_DIR, exist_ok=True)

async def save_upload_file(
    upload_file: UploadFile,
    media_dir: str = MEDIA_DIR,
    use_uuid: bool = True,
    date_subfolders: bool = True,
    max_size_bytes: int = MAX_SIZE_BYTES,
) -> tuple[str, str]:
    """
    Zapisuje UploadFile do dysku (asynchronicznie czyta plik po kawałku),
    zwraca (file_path_on_disk, public_url) — public_url zaczyna się od /media/...
    """
    if not upload_file:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No upload file provided")

    content_type = (upload_file.content_type or "").lower()
    if not content_type.startswith(ALLOWED_CONTENT_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Nieobsługiwany typ zawartości: {content_type}"
        )

    original_name = upload_file.filename or ""
    _, ext = os.path.splitext(original_name)
    ext = ext.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Nieobsługiwane rozszerzenie pliku: {ext}")

    filename = f"{uuid4().hex}{ext}" if use_uuid else original_name

    subpath = ""
    if date_subfolders:
        now = datetime.utcnow()
        subpath = os.path.join(str(now.year), f"{now.month:02d}", f"{now.day:02d}")

    target_dir = os.path.join(media_dir, subpath) if subpath else media_dir
    os.makedirs(target_dir, exist_ok=True)

    file_path = os.path.join(target_dir, filename)

    bytes_written = 0
    try:
        with open(file_path, "wb") as f:
            while True:
                chunk = await upload_file.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                bytes_written += len(chunk)
                if bytes_written > max_size_bytes:
                    f.close()
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Plik przekracza maksymalny rozmiar {MAX_SIZE_MB} MB."
                    )
    finally:
        try:
            await upload_file.close()
        except Exception:
            pass

    # zbuduj public_url używając forward-slash
    public_parts = []
    if subpath:
        for p in subpath.split(os.sep):
            if p:
                public_parts.append(p)
    public_parts.append(filename)
    public_url = "/media/" + "/".join(public_parts)

    return file_path, public_url
