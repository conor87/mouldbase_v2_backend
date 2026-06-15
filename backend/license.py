import base64
import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from fastapi import APIRouter, HTTPException, Request
from starlette.responses import JSONResponse


BASE_DIR = Path(__file__).resolve().parent
LICENSE_FILE = Path(os.getenv("LICENSE_FILE", BASE_DIR / "license.json"))
PUBLIC_KEY_FILE = Path(os.getenv("LICENSE_PUBLIC_KEY_FILE", BASE_DIR / "license_public_key.pem"))

LICENSE_EXCLUDED_PATHS = (
    "/license/status",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
)

router = APIRouter(prefix="/license", tags=["license"])


def _canonical_json(data: dict[str, Any]) -> bytes:
    return json.dumps(data, sort_keys=True).encode("utf-8")


def _parse_valid_until(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValueError("Pole valid_until musi miec format YYYY-MM-DD")


def _load_license_file() -> dict[str, Any]:
    if not LICENSE_FILE.exists():
        raise FileNotFoundError(f"Brak pliku licencji: {LICENSE_FILE}")

    with LICENSE_FILE.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    license_data = payload.get("license")
    signature = payload.get("signature")
    if not isinstance(license_data, dict) or not isinstance(signature, str):
        raise ValueError("Plik licencji musi zawierac pola license i signature")

    return payload


def _verify_signature(license_data: dict[str, Any], signature: str) -> None:
    if not PUBLIC_KEY_FILE.exists():
        raise FileNotFoundError(f"Brak klucza publicznego: {PUBLIC_KEY_FILE}")

    with PUBLIC_KEY_FILE.open("rb") as file:
        public_key = serialization.load_pem_public_key(file.read())

    public_key.verify(
        base64.b64decode(signature),
        _canonical_json(license_data),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH,
        ),
        hashes.SHA256(),
    )


def get_license_status() -> dict[str, Any]:
    try:
        payload = _load_license_file()
        license_data = payload["license"]
        _verify_signature(license_data, payload["signature"])

        valid_until = _parse_valid_until(license_data.get("valid_until"))
        today = date.today()
        days_remaining = (valid_until - today).days
        is_valid = days_remaining >= 0

        return {
            "valid": is_valid,
            "code": "active" if is_valid else "expired",
            "message": "Licencja aktywna" if is_valid else "Licencja wygasla",
            "customer": license_data.get("customer"),
            "app": license_data.get("app"),
            "valid_until": valid_until.isoformat(),
            "days_remaining": max(days_remaining, 0),
            "max_users": license_data.get("max_users"),
            "modules": license_data.get("modules", license_data.get("features", [])),
        }
    except FileNotFoundError as exc:
        return {"valid": False, "code": "missing", "message": str(exc)}
    except InvalidSignature:
        return {"valid": False, "code": "invalid_signature", "message": "Podpis licencji jest nieprawidlowy"}
    except Exception as exc:
        return {"valid": False, "code": "invalid", "message": f"Nieprawidlowa licencja: {exc}"}


def require_valid_license() -> None:
    status = get_license_status()
    if not status["valid"]:
        raise HTTPException(status_code=403, detail=status)


def is_license_excluded_path(path: str) -> bool:
    return path.startswith(LICENSE_EXCLUDED_PATHS)


@router.get("/status")
def license_status():
    return get_license_status()


async def license_middleware(request: Request, call_next):
    if request.method == "OPTIONS" or is_license_excluded_path(request.url.path):
        return await call_next(request)

    status = get_license_status()
    if not status["valid"]:
        return JSONResponse(status_code=403, content={"detail": status})

    return await call_next(request)
