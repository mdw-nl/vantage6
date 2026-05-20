"""Local-filesystem backend for the large result store.

Blobs are written under a configurable ``base_path`` using a two-character
shard derived from the blob name: ``{base_path}/{name[:2]}/{name}``. This
keeps any single directory's fan-out bounded while still being trivial
to reason about.

Writes are atomic: a tempfile is written in the same shard directory,
``fsync``-ed, and then ``os.replace``-d into place, so readers never
observe a half-written blob. For multi-replica deployments ``base_path``
must point at a shared filesystem (NFS, Azure Files, …) — otherwise
replicas will not see each other's blobs.
"""

import logging
import os
import re
import tempfile
from pathlib import Path
from typing import IO, Iterator, Union

from vantage6.common import logger_name
from vantage6.common.globals import DEFAULT_CHUNK_SIZE
from vantage6.server.service.storage_adapter import BlobStream, StorageAdapter

module_name = logger_name(__name__)
log = logging.getLogger(module_name)

_BLOB_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
BLOB_BASE_PATH_ENV_VAR = "VANTAGE6_BLOB_BASE_PATH"


class FileBlobStream(BlobStream):
    """Streaming reader for a blob stored on the local filesystem."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def chunks(self) -> Iterator[bytes]:
        with self._path.open("rb") as f:
            while True:
                chunk = f.read(DEFAULT_CHUNK_SIZE)
                if not chunk:
                    return
                yield chunk


class FileStorageService(StorageAdapter):
    """Filesystem-backed implementation of :class:`StorageAdapter`."""

    def __init__(self, config: dict) -> None:
        base_path = os.environ.get(BLOB_BASE_PATH_ENV_VAR) or config.get("base_path")
        if not base_path:
            raise ValueError(
                "File storage base path must be provided via the "
                f"{BLOB_BASE_PATH_ENV_VAR} environment variable or the "
                "'base_path' key of the large_result_store config."
            )

        root = Path(base_path).expanduser().resolve()
        container_name = config.get("container_name")
        if container_name:
            if not _BLOB_NAME_RE.match(container_name):
                raise ValueError(
                    f"Invalid container_name {container_name!r}: must match {_BLOB_NAME_RE.pattern}"
                )
            root = root / container_name

        root.mkdir(parents=True, exist_ok=True)
        if not os.access(root, os.W_OK):
            log.warning("File storage base path %s is not writable.", root)

        self.base_path = root
        log.info("File storage adapter initialised at %s", self.base_path)
        super().__init__(config)

    def _path_for(self, blob_name: str) -> Path:
        if not isinstance(blob_name, str) or not _BLOB_NAME_RE.match(blob_name):
            raise ValueError(f"Invalid blob name: {blob_name!r}")
        return self.base_path / blob_name[:2] / blob_name

    def get_blob(self, blob_name: str) -> bytes:
        path = self._path_for(blob_name)
        log.debug("Retrieving blob: %s", path)
        return path.read_bytes()

    def store_blob(self, blob_name: str, data: Union[IO, bytes]) -> None:
        target = self._path_for(blob_name)
        log.debug("Storing blob: %s", target)
        target.parent.mkdir(parents=True, exist_ok=True)

        tmp = tempfile.NamedTemporaryFile(
            dir=target.parent, prefix=".tmp-", suffix=f"-{blob_name}", delete=False
        )
        tmp_path = Path(tmp.name)
        try:
            if isinstance(data, (bytes, bytearray, memoryview)):
                tmp.write(bytes(data))
            else:
                while True:
                    chunk = data.read(DEFAULT_CHUNK_SIZE)
                    if not chunk:
                        break
                    tmp.write(chunk)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp.close()
            os.replace(tmp_path, target)
            self._fsync_dir(target.parent)
        except Exception as e:
            try:
                tmp.close()
            except Exception:
                pass
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
            log.error("Failed to store blob %r: %s", blob_name, e)
            raise RuntimeError(f"Failed to store blob {blob_name!r}: {e}") from e

    def delete_blob(self, blob_name: str) -> None:
        path = self._path_for(blob_name)
        log.debug("Deleting blob: %s", path)
        path.unlink(missing_ok=True)
        try:
            path.parent.rmdir()
        except OSError:
            pass

    def stream_blob(self, blob_name: str) -> FileBlobStream:
        path = self._path_for(blob_name)
        log.debug("Streaming blob: %s", path)
        if not path.exists():
            raise FileNotFoundError(f"Blob {blob_name!r} not found at {path}")
        return FileBlobStream(path)

    @staticmethod
    def _fsync_dir(directory: Path) -> None:
        try:
            fd = os.open(directory, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(fd)
        except OSError:
            pass
        finally:
            os.close(fd)
