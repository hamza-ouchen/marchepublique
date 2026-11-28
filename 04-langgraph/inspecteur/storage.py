# =====================================================================
# Upload Supabase Storage (REST, sans SDK) pour les CPS.
# Utilise SUPABASE_URL + SUPABASE_SERVICE_KEY (service_role).
# =====================================================================
from __future__ import annotations

import base64
import os
import re
import threading
import time
from typing import Callable
from urllib.parse import quote, urljoin, urlsplit

import requests

# config minimale (env vars)
class _Config:
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

config = _Config()
_http = threading.local()
_TUS_CHUNK = 6 * 1024 * 1024


def _creds() -> tuple[str, str] | None:
    url = os.getenv("SUPABASE_URL") or getattr(config, "SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or config.SUPABASE_SERVICE_KEY
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
    if not hasattr(_http, "session"):
        _http.session = requests.Session()
    for attempt in range(3):
        try:
            if len(data) > _TUS_CHUNK:
                _upload_resumable(base, key, bucket, path, data, content_type)
                return path
            with _http.session.post(endpoint, headers=headers, data=data, timeout=120) as response:
                if response.status_code in (200, 201):
                    return path
                if response.status_code not in (429, 502, 503, 504) or attempt == 2:
                    raise RuntimeError(f"upload failed {response.status_code}: {response.text[:300]}")
        except (requests.ConnectionError, requests.Timeout):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)


def _upload_resumable(base, key, bucket, path, data, content_type):
    host = urlsplit(base).hostname or ""
    if re.fullmatch(r"[a-z0-9]+\.supabase\.co", host):
        base = f"https://{host.split('.')[0]}.storage.supabase.co"
    endpoint = f"{base}/storage/v1/upload/resumable"
    headers = {"Authorization": f"Bearer {key}", "apikey": key,
               "Tus-Resumable": "1.0.0", "x-upsert": "true"}
    metadata = ",".join(
        f"{name} {base64.b64encode(value.encode()).decode()}"
        for name, value in (("bucketName", bucket), ("objectName", path),
                            ("contentType", content_type), ("cacheControl", "3600"))
    )
    session = _http.session
    with session.post(endpoint, headers={**headers, "Upload-Metadata": metadata,
                                         "Upload-Length": str(len(data))}, timeout=45,
                      allow_redirects=False) as started:
        if started.status_code != 201 or not started.headers.get("Location"):
            raise RuntimeError(f"resumable upload creation failed: HTTP {started.status_code}")
        location = urljoin(endpoint, started.headers["Location"])
    if urlsplit(location).netloc != urlsplit(endpoint).netloc:
        raise RuntimeError("Unexpected resumable upload host")
    offset = 0
    failures = 0
    while offset < len(data):
        chunk = data[offset:offset + _TUS_CHUNK]
        try:
            with session.patch(location, data=chunk, timeout=120, allow_redirects=False,
                               headers={**headers, "Upload-Offset": str(offset),
                                        "Content-Type": "application/offset+octet-stream"}) as response:
                if response.status_code != 204:
                    raise requests.HTTPError(f"resumable upload chunk failed: HTTP {response.status_code}")
                next_offset = int(response.headers["Upload-Offset"])
                if next_offset != offset + len(chunk):
                    raise RuntimeError("Unexpected resumable upload offset")
                offset = next_offset
                failures = 0
        except requests.RequestException:
            failures += 1
            if failures > 2:
                raise
            with session.head(location, headers=headers, timeout=45, allow_redirects=False) as state:
                state.raise_for_status()
                next_offset = int(state.headers["Upload-Offset"])
                if not offset <= next_offset <= offset + len(chunk):
                    raise RuntimeError("Unexpected resumable upload retry offset")
                offset = next_offset


def make_uploader(bucket: str = "cps-originaux") -> Callable[[str, bytes], str] | None:
    """Retourne un callable compatible cps_ingest.storage_uploader, ou None
    si les credentials Supabase sont absents (mode dégradé : pas d'upload)."""
    creds = _creds()
    if creds is None:
        return None

    if os.getenv("SOU9NA_STORE_TENDER_ORIGINALS", "0") != "1":
        return None

    def _uploader(path: str, data: bytes) -> str:
        return upload_bytes(bucket, path, data)

    return _uploader


def download_bytes(bucket: str, path: str, limit: int = 50 * 1024 * 1024) -> bytes:
    creds = _creds()
    if creds is None:
        raise RuntimeError("Supabase Storage credentials are required")
    base, key = creds
    endpoint = f"{base}/storage/v1/object/authenticated/{quote(bucket, safe='')}/{quote(path)}"
    headers = {"Authorization": f"Bearer {key}", "apikey": key}
    with requests.get(endpoint, headers=headers, timeout=120, stream=True) as response:
        response.raise_for_status()
        data = bytearray()
        for chunk in response.iter_content(64 * 1024):
            data.extend(chunk)
            if len(data) > limit:
                raise ValueError("Stored object exceeds the document size limit")
    return bytes(data)


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
