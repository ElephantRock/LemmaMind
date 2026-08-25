"""Content-addressed byte storage for captured source artifacts."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path


class ObjectCorruption(RuntimeError):
    """Raised when bytes on disk do not match the digest in their object path."""


class ContentAddressedFileStore:
    """Minimal immutable object store keyed by SHA-256.

    Remote source paths never participate in local filesystem layout. The only
    local key is a validated content digest, which keeps untrusted repository
    filenames from controlling where bytes are written.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def digest(data: bytes) -> str:
        return f"sha256:{hashlib.sha256(data).hexdigest()}"

    def _path(self, digest: str) -> Path:
        algorithm, separator, hex_digest = digest.partition(":")
        if (
            algorithm != "sha256"
            or not separator
            or len(hex_digest) != 64
            or any(character not in "0123456789abcdef" for character in hex_digest)
        ):
            raise ValueError("digest must be sha256:<64 lowercase hex chars>")
        return self.root / "sha256" / hex_digest[:2] / hex_digest[2:]

    def put(self, data: bytes) -> str:
        """Store bytes immutably and return their content digest."""

        digest = self.digest(data)
        path = self._path(digest)
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists():
            existing = path.read_bytes()
            if self.digest(existing) != digest:
                raise ObjectCorruption(f"object at {path} does not match {digest}")
            return digest

        file_descriptor, temporary_name = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
        try:
            with os.fdopen(file_descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
        return digest

    def get(self, digest: str) -> bytes:
        """Read and verify one object."""

        path = self._path(digest)
        data = path.read_bytes()
        if self.digest(data) != digest:
            raise ObjectCorruption(f"object at {path} does not match {digest}")
        return data

    def exists(self, digest: str) -> bool:
        return self._path(digest).exists()
