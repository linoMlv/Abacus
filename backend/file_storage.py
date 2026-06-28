"""File storage abstraction and strict upload validation for justificatifs.

Design (security-first, plan §15.7):

* **Abstraction** — :class:`FileStorage` hides where bytes live. The local
  implementation writes under a base directory (a container volume); switching
  to S3/MinIO later is a new implementation, no caller change.
* **No path traversal** — storage keys are server-generated and validated to be
  plain relative paths; a client filename never reaches the filesystem path.
* **Trust the bytes, not the client** — the accepted content type is sniffed
  from the file's magic bytes, never taken from the request's declared type.
  Only PDF and common raster images are allowed; SVG/HTML are refused (they can
  carry active content / XSS).
* **Bounded size** — uploads are read with a hard cap, so a large body cannot
  exhaust memory.
"""

from abc import ABC, abstractmethod
from pathlib import Path

# 5 MiB hard cap on a single justificatif.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

# Allowed types, keyed by the canonical content type we will store and serve.
# SVG and HTML are deliberately absent: they can execute script in a browser.
_MAGIC_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"%PDF-", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


def detect_content_type(head: bytes) -> str | None:
    """Return the canonical content type sniffed from ``head``, or ``None``.

    Only the file's leading bytes are inspected. WEBP needs a two-part check
    (``RIFF`` container + ``WEBP`` fourcc). Anything not recognised — including
    SVG, HTML and arbitrary text — yields ``None`` and must be rejected.
    """
    for signature, content_type in _MAGIC_SIGNATURES:
        if head.startswith(signature):
            return content_type
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return None


def _safe_key(key: str) -> str:
    """Validate a server-generated storage key is a plain relative path."""
    pure = Path(key)
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"Unsafe storage key: {key!r}")
    return key


class FileStorage(ABC):
    """A place to persist opaque blobs addressed by a server-generated key."""

    @abstractmethod
    def save(self, key: str, data: bytes) -> None:
        ...

    @abstractmethod
    def load(self, key: str) -> bytes:
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        ...


class LocalFileStorage(FileStorage):
    """Stores blobs as files under ``base_dir`` (a container volume)."""

    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)

    def _path(self, key: str) -> Path:
        return self.base_dir / _safe_key(key)

    def save(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def load(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


def _build_default_storage() -> FileStorage:
    import os

    base_dir = os.getenv("STORAGE_DIR", "./var/justificatifs")
    return LocalFileStorage(base_dir)


_default_storage: FileStorage | None = None


def get_storage() -> FileStorage:
    """FastAPI dependency returning the process-wide storage (overridable in tests)."""
    global _default_storage
    if _default_storage is None:
        _default_storage = _build_default_storage()
    return _default_storage
