# =====================================================================
# Upload Supabase Storage (REST, sans SDK) pour les CPS.
# Utilise SUPABASE_URL + SUPABASE_SERVICE_KEY (service_role).
# =====================================================================
from __future__ import annotations

import os
from typing import Callable

import requests

from app import config


def _creds() -> tuple[str, str] | None:
    url = os.getenv("SUPABASE_URL") or getattr(config, "SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY") or getattr(config, "SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        return None
    return url.rstrip("/"), key


def upload_bytes(bucket: str, path: str, data: bytes,
                 content_type: str = "application/pdf") -> str:
    """Upload un fichier dans un bucket Supabase Storage.

    Retourne le storage_path (chemin dans le bucket).
    Lève RuntimeError si les credentials sont absents ou l'upload échoue.
    """
    creds = _creds()
    if creds is None:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_KEY manquants")
    base, key = creds
    endpoint = f"{base}/storage/v1/object/{bucket}/{path}"
    headers = {
        "Authorization": f"Bearer {key}",
        "apikey": key,
        "Content-Type": content_type,
        "x-upsert": "true",
    }
    resp = requests.post(endpoint, headers=headers, data=data, timeout=120)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"upload failed {resp.status_code}: {resp.text[:300]}")
    return path


def make_uploader(bucket: str = "cps-originaux") -> Callable[[str, bytes], str] | None:
    """Retourne un callable compatible cps_ingest.storage_uploader, ou None
    si les credentials Supabase sont absents (mode dégradé : pas d'upload)."""
    creds = _creds()
    if creds is None:
        return None

    def _uploader(path: str, data: bytes) -> str:
        return upload_bytes(bucket, path, data)

    return _uploader


def delete_object(bucket: str, path: str) -> bool:
    creds = _creds()
    if creds is None:
        return False
    base, key = creds
    resp = requests.delete(
        f"{base}/storage/v1/object/{bucket}/{path}",
        headers={"Authorization": f"Bearer {key}", "apikey": key},
        timeout=30,
    )
    return resp.status_code in (200, 204)