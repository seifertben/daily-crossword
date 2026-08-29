"""Puzzle storage: local disk (dev/static) or Cloud Storage (prod).

The generation job writes one immutable ``puzzles/YYYY-MM-DD.json`` per day; the
serving app reads them. Both ends talk to a :class:`PuzzleStore` so the rest of
the code is storage-agnostic. The ``static`` store writes into a Vite public dir
so a fully static build can serve the same puzzles without any backend.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol


class PuzzleStore(Protocol):
    def put(self, date: str, payload: str) -> None: ...
    def get(self, date: str) -> str | None: ...
    def exists(self, date: str) -> bool: ...
    def list_dates(self) -> list[str]: ...


def _date_path(date: str) -> str:
    if not date or any(ch not in "0123456789-" for ch in date):
        raise ValueError(f"bad date: {date!r}")
    return f"puzzles/{date}.json"


class LocalStore:
    """On-disk store under ``LOCAL_DATA_DIR/puzzles/`` (default ./local-data)."""

    def __init__(self, root: str | os.PathLike[str] | None = None) -> None:
        base = Path(root) if root else Path(os.environ.get("LOCAL_DATA_DIR", "./local-data"))
        self._root = base.resolve()
        (self._root / "puzzles").mkdir(parents=True, exist_ok=True)

    def _path(self, date: str) -> Path:
        return self._root / _date_path(date)

    def put(self, date: str, payload: str) -> None:
        path = self._path(date)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")

    def get(self, date: str) -> str | None:
        path = self._path(date)
        return path.read_text(encoding="utf-8") if path.exists() else None

    def exists(self, date: str) -> bool:
        return self._path(date).exists()

    def list_dates(self) -> list[str]:
        puzzle_dir = self._root / "puzzles"
        if not puzzle_dir.exists():
            return []
        return sorted(p.stem for p in puzzle_dir.glob("*.json"))


class GCSStore:
    """Cloud Storage backed store (production).

    Lazily imports ``google-cloud-storage`` so local dev never needs it.
    """

    def __init__(self, bucket: str, *, prefix: str = "") -> None:
        try:
            from google.cloud import storage  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - exercised in prod only
            raise RuntimeError(
                "google-cloud-storage is required for PUZZLE_STORE=gcs; "
                "install it in the generation/serving image."
            ) from exc
        self._client = storage.Client()
        self._bucket = self._client.bucket(bucket)
        self._prefix = prefix.strip("/")

    def _key(self, date: str) -> str:
        rel = _date_path(date)
        return f"{self._prefix}/{rel}" if self._prefix else rel

    def put(self, date: str, payload: str) -> None:
        blob = self._bucket.blob(self._key(date))
        blob.cache_control = "public, max-age=31536000"
        blob.upload_from_string(payload, content_type="application/json")

    def get(self, date: str) -> str | None:
        blob = self._bucket.blob(self._key(date))
        if not blob.exists():
            return None
        return str(blob.download_as_text(encoding="utf-8"))

    def exists(self, date: str) -> bool:
        return bool(self._bucket.blob(self._key(date)).exists())

    def list_dates(self) -> list[str]:
        prefix = f"{self._prefix}/puzzles/" if self._prefix else "puzzles/"
        return sorted(
            b.name.rsplit("/", 1)[-1].removesuffix(".json")
            for b in self._bucket.list_blobs(prefix=prefix)
            if b.name.endswith(".json")
        )


def get_store() -> PuzzleStore:
    """Build a store from env.

    ``PUZZLE_STORE`` = ``local`` (default scratch store) | ``static`` (puzzles
    written under a Vite public dir so a static build ships them verbatim)
    | ``gcs`` (Cloud Storage, production).
    """
    kind = os.environ.get("PUZZLE_STORE", "local").strip().lower()
    if kind == "gcs":
        bucket = os.environ.get("PUZZLE_BUCKET", "").strip()
        if not bucket:
            raise RuntimeError("PUZZLE_STORE=gcs requires PUZZLE_BUCKET")
        return GCSStore(bucket)
    if kind == "static":
        root = os.environ.get("STATIC_PUZZLE_DIR", "./web/public")
        return LocalStore(root)
    return LocalStore()
