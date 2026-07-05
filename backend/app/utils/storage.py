"""Thin client for a *private* Supabase Storage bucket.

Only the backend ever talks to the bucket, using the service-role key. Clinical
photos are uploaded here and streamed back through an authenticated endpoint
(routes/treatments.py) — the bucket is never public and no signed URLs are
handed to the browser, so tenant isolation for the image bytes rides entirely
on our own auth + RLS layer (an image row can only be read under its owning
clinic's scope, and only then do we fetch its bytes).

Configuration (env vars, see backend/.env.example):
  SUPABASE_URL             e.g. https://xxxxxxxx.supabase.co
  SUPABASE_SERVICE_KEY     the service_role key (NEVER expose to the frontend)
  SUPABASE_STORAGE_BUCKET  bucket name (default: treatment-images)

If these aren't set, is_configured() returns False and the routes respond 503
with a clear message instead of failing obscurely.
"""
import os
import requests

REQUEST_TIMEOUT = 30  # seconds


class StorageError(Exception):
    """Raised when the Supabase Storage API returns a non-success response."""


def _base_url() -> str:
    return (os.getenv("SUPABASE_URL") or "").rstrip("/")


def _service_key() -> str:
    return os.getenv("SUPABASE_SERVICE_KEY") or ""


def bucket() -> str:
    return os.getenv("SUPABASE_STORAGE_BUCKET") or "treatment-images"


def is_configured() -> bool:
    return bool(_base_url() and _service_key())


def _headers(extra: dict | None = None) -> dict:
    h = {
        "Authorization": f"Bearer {_service_key()}",
        "apikey": _service_key(),
    }
    if extra:
        h.update(extra)
    return h


def _object_endpoint(path: str) -> str:
    return f"{_base_url()}/storage/v1/object/{bucket()}/{path}"


def upload_object(path: str, data: bytes, content_type: str) -> None:
    """Create/overwrite an object at `path` inside the bucket."""
    resp = requests.post(
        _object_endpoint(path),
        headers=_headers({
            "Content-Type": content_type or "application/octet-stream",
            "x-upsert": "true",
            "cache-control": "3600",
        }),
        data=data,
        timeout=REQUEST_TIMEOUT,
    )
    if resp.status_code not in (200, 201):
        raise StorageError(f"Upload failed ({resp.status_code}): {resp.text[:300]}")


def download_object(path: str) -> bytes:
    """Fetch the raw bytes of an object. Raises StorageError on any non-200."""
    resp = requests.get(
        _object_endpoint(path),
        headers=_headers(),
        timeout=REQUEST_TIMEOUT,
    )
    if resp.status_code != 200:
        raise StorageError(f"Download failed ({resp.status_code}): {resp.text[:300]}")
    return resp.content


def delete_object(path: str) -> None:
    """Remove an object. A 404 (already gone) is treated as success so a
    dangling row can always be cleaned up."""
    resp = requests.delete(
        _object_endpoint(path),
        headers=_headers(),
        timeout=REQUEST_TIMEOUT,
    )
    if resp.status_code not in (200, 204, 404):
        raise StorageError(f"Delete failed ({resp.status_code}): {resp.text[:300]}")
