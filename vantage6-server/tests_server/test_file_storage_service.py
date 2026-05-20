"""Tests for the local-filesystem large-result-store backend."""

import io
import os
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from vantage6.common.globals import DEFAULT_CHUNK_SIZE
from vantage6.server.service.file_storage_service import (
    BLOB_BASE_PATH_ENV_VAR,
    FileStorageService,
)


@pytest.fixture
def adapter(tmp_path: Path) -> FileStorageService:
    return FileStorageService({"base_path": str(tmp_path)})


def _uuid() -> str:
    return str(uuid.uuid4())


def test_bytes_roundtrip(adapter: FileStorageService) -> None:
    name = _uuid()
    payload = b"hello world"
    adapter.store_blob(name, payload)
    assert adapter.get_blob(name) == payload


def test_stream_roundtrip(adapter: FileStorageService) -> None:
    name = _uuid()
    # Span several read chunks with a non-aligned tail to exercise partial reads.
    payload = b"x" * (3 * DEFAULT_CHUNK_SIZE + 17)
    adapter.store_blob(name, payload)

    chunks = list(adapter.stream_blob(name).chunks())
    assert b"".join(chunks) == payload
    assert all(c for c in chunks)


def test_iostream_roundtrip(adapter: FileStorageService) -> None:
    name = _uuid()
    # Span several write chunks with a non-aligned tail to exercise partial writes.
    payload = os.urandom(3 * DEFAULT_CHUNK_SIZE + 17)
    adapter.store_blob(name, io.BytesIO(payload))
    assert adapter.get_blob(name) == payload


def test_sharded_layout(adapter: FileStorageService, tmp_path: Path) -> None:
    name = _uuid()
    adapter.store_blob(name, b"x")
    assert (tmp_path / name[:2] / name).is_file()


def test_container_subdir(tmp_path: Path) -> None:
    adapter = FileStorageService(
        {"base_path": str(tmp_path), "container_name": "results"}
    )
    name = _uuid()
    adapter.store_blob(name, b"x")
    assert (tmp_path / "results" / name[:2] / name).is_file()


def test_delete_idempotent(adapter: FileStorageService) -> None:
    name = _uuid()
    adapter.delete_blob(name)  # missing — should not raise
    adapter.store_blob(name, b"x")
    adapter.delete_blob(name)
    assert not (adapter.base_path / name[:2] / name).exists()
    adapter.delete_blob(name)  # idempotent after delete


def test_atomic_write_crash_safety(adapter: FileStorageService) -> None:
    name = _uuid()
    with patch(
        "vantage6.server.service.file_storage_service.os.replace",
        side_effect=OSError("simulated crash"),
    ):
        with pytest.raises(RuntimeError):
            adapter.store_blob(name, b"payload")

    shard = adapter.base_path / name[:2]
    target = shard / name
    assert not target.exists()
    if shard.exists():
        assert not any(p.name.startswith(".tmp-") for p in shard.iterdir())


def test_path_traversal_rejected(adapter: FileStorageService) -> None:
    with pytest.raises(ValueError):
        adapter.store_blob("../etc/passwd", b"x")
    with pytest.raises(ValueError):
        adapter.store_blob("a/b", b"x")
    with pytest.raises(ValueError):
        adapter.get_blob("")


def test_missing_base_path_rejected() -> None:
    with pytest.raises(ValueError):
        FileStorageService({})


def test_env_var_overrides_config_base_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_path = tmp_path / "env-dir"
    config_path = tmp_path / "config-dir"
    monkeypatch.setenv(BLOB_BASE_PATH_ENV_VAR, str(env_path))

    adapter = FileStorageService({"base_path": str(config_path)})

    assert adapter.base_path == env_path.resolve()
    assert env_path.is_dir()
    assert not config_path.exists()


def test_env_var_used_when_config_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(BLOB_BASE_PATH_ENV_VAR, str(tmp_path))
    adapter = FileStorageService({})
    assert adapter.base_path == tmp_path.resolve()


def test_stream_missing_blob_raises(adapter: FileStorageService) -> None:
    with pytest.raises(FileNotFoundError):
        adapter.stream_blob(_uuid())


def test_get_missing_blob_raises(adapter: FileStorageService) -> None:
    with pytest.raises(FileNotFoundError):
        adapter.get_blob(_uuid())
