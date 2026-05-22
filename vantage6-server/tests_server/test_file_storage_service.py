"""Tests for the local-filesystem large-result-store backend."""

import io
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from vantage6.common.globals import DEFAULT_CHUNK_SIZE
from vantage6.server.service.file_storage_service import (
    DEFAULT_RUN_DATA_BASE_PATH,
    RUN_DATA_BASE_PATH_ENV_VAR,
    FileStorageService,
)
from vantage6.server.service.storage_adapter import build_storage_adapter


def _uuid() -> str:
    return str(uuid.uuid4())


class TestFileStorageService(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.adapter = FileStorageService({}, base_path=self.tmp_path)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_bytes_roundtrip(self) -> None:
        name = _uuid()
        payload = b"hello world"
        self.adapter.store_run_data(name, payload)
        self.assertEqual(self.adapter.get_run_data(name), payload)

    def test_stream_roundtrip(self) -> None:
        name = _uuid()
        # Span several read chunks with a non-aligned tail to exercise partial reads.
        payload = b"x" * (3 * DEFAULT_CHUNK_SIZE + 17)
        self.adapter.store_run_data(name, payload)

        chunks = list(self.adapter.stream_run_data(name).chunks())
        self.assertEqual(b"".join(chunks), payload)
        self.assertTrue(all(c for c in chunks))

    def test_iostream_roundtrip(self) -> None:
        name = _uuid()
        # Span several write chunks with a non-aligned tail to exercise partial writes.
        payload = os.urandom(3 * DEFAULT_CHUNK_SIZE + 17)
        self.adapter.store_run_data(name, io.BytesIO(payload))
        self.assertEqual(self.adapter.get_run_data(name), payload)

    def test_sharded_layout(self) -> None:
        name = _uuid()
        self.adapter.store_run_data(name, b"x")
        self.assertTrue((self.tmp_path / name[:2] / name).is_file())

    def test_delete_idempotent(self) -> None:
        name = _uuid()
        self.adapter.delete_run_data(name)  # missing — should not raise
        self.adapter.store_run_data(name, b"x")
        self.adapter.delete_run_data(name)
        self.assertFalse((self.adapter.base_path / name[:2] / name).exists())
        self.adapter.delete_run_data(name)  # idempotent after delete

    def test_atomic_write_crash_safety(self) -> None:
        name = _uuid()
        with patch(
            "vantage6.server.service.file_storage_service.os.replace",
            side_effect=OSError("simulated crash"),
        ):
            with self.assertRaises(RuntimeError):
                self.adapter.store_run_data(name, b"payload")

        shard = self.adapter.base_path / name[:2]
        target = shard / name
        self.assertFalse(target.exists())
        if shard.exists():
            self.assertFalse(
                any(p.name.startswith(".tmp-") for p in shard.iterdir())
            )

    def test_path_traversal_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.adapter.store_run_data("../etc/passwd", b"x")
        with self.assertRaises(ValueError):
            self.adapter.store_run_data("a/b", b"x")
        with self.assertRaises(ValueError):
            self.adapter.get_run_data("")

    def test_base_path_resolved(self) -> None:
        adapter = FileStorageService({}, base_path=self.tmp_path)
        self.assertEqual(adapter.base_path, self.tmp_path.resolve())

    def test_stream_missing_run_data_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            self.adapter.stream_run_data(_uuid())

    def test_get_missing_run_data_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            self.adapter.get_run_data(_uuid())


class TestStorageAdapterFactory(unittest.TestCase):
    def test_factory_returns_none_when_unset(self) -> None:
        self.assertIsNone(build_storage_adapter({}))

    def test_factory_uses_env_var_for_base_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {RUN_DATA_BASE_PATH_ENV_VAR: tmp}):
                adapter = build_storage_adapter(
                    {"large_run_data_store": "filesystem"}
                )
            self.assertIsInstance(adapter, FileStorageService)
            self.assertEqual(adapter.base_path, Path(tmp).resolve())

    def test_factory_falls_back_to_default_when_env_unset(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != RUN_DATA_BASE_PATH_ENV_VAR}
        with patch.dict(os.environ, env, clear=True):
            with patch(
                "vantage6.server.service.file_storage_service.Path.mkdir"
            ) as mock_mkdir:
                adapter = build_storage_adapter(
                    {"large_run_data_store": "filesystem"}
                )
        self.assertIsInstance(adapter, FileStorageService)
        self.assertEqual(
            adapter.base_path, Path(DEFAULT_RUN_DATA_BASE_PATH).resolve()
        )
        mock_mkdir.assert_called()

    def test_factory_rejects_deprecated_large_result_store_key(self) -> None:
        with self.assertRaises(ValueError) as cm:
            build_storage_adapter({"large_result_store": {"type": "file"}})
        self.assertIn("large_result_store", str(cm.exception))

    def test_factory_rejects_unknown_store_type(self) -> None:
        with self.assertRaises(ValueError):
            build_storage_adapter({"large_run_data_store": "s3"})

    def test_factory_rejects_azure_without_block(self) -> None:
        with self.assertRaises(ValueError) as cm:
            build_storage_adapter({"large_run_data_store": "azure"})
        self.assertIn("azure_run_data_store", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
