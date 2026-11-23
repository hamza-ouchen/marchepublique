# =====================================================================
# Upload optionnel des PDF originaux dans Supabase Storage (REST, sans SDK).
# Désactivé par défaut (CPS_STORE_ORIGINALS=false) pour le free tier.
# =====================================================================
from __future__ import annotations

from typing import Callable

import requests

from . import config


def upload_bytes(bucket: str, path: str, data: bytes,
                 content_type: str = "application/pdf") -> str:
    if not config.SUPABASE_URL or not config.SUPABASE_SERVICE_KEY:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_KEY manquants")
    resp = requests.post(
        f"{config.SUPABASE_URL}/storage/v1/object/{bucket}/{path}",
        headers={
            "Authorization": f"Bearer {config.SUPABASE_SERVICE_KEY}",
            "apikey": config.SUPABASE_SERVICE_KEY,
            "Content-Type": content_type,
            "x-upsert": "true",
        },
        data=data,
        timeout=120,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"upload {resp.status_code}: {resp.text[:200]}")
    return path


def make_uploader(bucket: str | None = None
                  ) -> Callable[[str, bytes], str] | None:
    if not config.SUPABASE_URL or not config.SUPABASE_SERVICE_KEY:
        return None
    target = bucket or config.BUCKET

    def _upload(path: str, data: bytes) -> str:
        return upload_bytes(target, path, data)

    return _upload
