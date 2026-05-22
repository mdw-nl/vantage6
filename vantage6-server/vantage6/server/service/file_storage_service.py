"""Local-filesystem backend for the large result store.

Run-data entries are written under ``base_path`` using a two-character
shard derived from the name: ``{base_path}/{name[:2]}/{name}``. This
keeps any single directory's fan-out bounded while still being trivial
to reason about.

``base_path`` is supplied by the caller. The factory in
:mod:`vantage6.server.service.storage_adapter` resolves it from the
``VANTAGE6_RUN_DATA_BASE_PATH`` environment variable, defaulting to
``/mnt/run_data``. Operators control where run data lives by mounting
that path into the server container (the ``v6 server start`` CLI does
this automatically; under docker-compose the user adds a volume mount
themselves).

Writes are atomic: a tempfile is written in the same shard directory,
``fsync``-ed, and then ``os.replace``-d into place, so readers never
observe a half-written entry. For multi-replica deployments the mount
target must point at a shared filesystem (NFS, Azure Files, …) —
otherwise replicas will not see each other's run data.
"""

import logging
import os
import re
import tempfile
from pathlib import Path
from typing import IO, Iterator, Union

from vantage6.common import logger_name
from vantage6.common.globals import DEFAULT_CHUNK_SIZE
from vantage6.server.service.storage_adapter import (
    RunDataNotFoundError,
    RunDataStream,
    StorageAdapter,
)

module_name = logger_name(__name__)
log = logging.getLogger(module_name)

_RUN_DATA_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
RUN_DATA_BASE_PATH_ENV_VAR = "VANTAGE6_RUN_DATA_BASE_PATH"
DEFAULT_RUN_DATA_BASE_PATH = "/mnt/run_data"


class FileRunDataStream(RunDataStream):
    """Streaming reader for run data stored on the local filesystem."""

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

    def __init__(self, config: dict, base_path: str | Path) -> None:
        root = Path(base_path).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        if not os.access(root, os.W_OK):
            log.warning("File storage base path %s is not writable.", root)

        self.base_path = root
        log.info("File storage adapter initialised at %s", self.base_path)
        super().__init__(config)

    def _path_for(self, name: str) -> Path:
        if not isinstance(name, str) or not _RUN_DATA_NAME_RE.match(name):
            raise ValueError(f"Invalid run-data name: {name!r}")
        return self.base_path / name[:2] / name

    def get_run_data(self, name: str) -> bytes:
        path = self._path_for(name)
        log.debug("Retrieving run data: %s", path)
        try:
            return path.read_bytes()
        except FileNotFoundError as e:
            raise RunDataNotFoundError(
                f"Run data {name!r} not found at {path}"
            ) from e

    def store_run_data(self, name: str, data: Union[IO, bytes]) -> None:
        """Atomically write ``data`` under ``name``.

        The recipe below ("write tempfile in the same dir, fsync, rename,
        fsync the dir") is the standard POSIX atomic-write pattern. Each
        step is load-bearing:

        - **Tempfile in the same shard directory.** ``os.replace`` only
          guarantees atomicity within a single filesystem; writing to
          ``/tmp`` first and then renaming risks an ``EXDEV`` cross-device
          error. ``prefix=".tmp-"`` makes incomplete uploads recognisable
          to cleanup tooling (and to the test that scans for leftovers).
        - **``flush + fsync`` before the rename.** Without ``fsync``, the
          file's data may still live in the kernel page cache when
          ``os.replace`` swings the directory entry. A power-loss between
          the rename and the eventual writeback would leave a zero-byte
          or truncated file under ``target``.
        - **``os.replace`` (not ``Path.rename``).** ``os.replace`` is
          atomic and overwrites the destination if it already exists,
          which matters because callers occasionally re-upload the same
          UUID. ``Path.rename`` raises on POSIX if the target exists.
        - **``_fsync_dir`` after the rename.** The rename itself is a
          directory-entry change, and on most filesystems that change is
          also buffered. Fsyncing the parent directory makes the new
          name durable across a crash.
        - **Cleanup in ``except``.** Any failure (write error, OOM, the
          ``os.replace`` mock in the crash-safety test) must remove the
          tempfile so we don't leak ``.tmp-*`` files that confuse
          operators and the leftover-tempfile test.
        """
        target = self._path_for(name)
        log.debug("Storing run data: %s", target)
        target.parent.mkdir(parents=True, exist_ok=True)

        tmp = tempfile.NamedTemporaryFile(
            dir=target.parent, prefix=".tmp-", suffix=f"-{name}", delete=False
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
            # Tempfile cleanup must be best-effort: the original failure
            # is what we want to surface, not a secondary close/unlink
            # error masking it.
            try:
                tmp.close()
            except Exception:
                pass
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
            log.error("Failed to store run data %r: %s", name, e)
            raise RuntimeError(f"Failed to store run data {name!r}: {e}") from e

    def delete_run_data(self, name: str) -> None:
        path = self._path_for(name)
        log.debug("Deleting run data: %s", path)
        path.unlink(missing_ok=True)
        try:
            path.parent.rmdir()
        except OSError:
            pass

    def stream_run_data(self, name: str) -> FileRunDataStream:
        path = self._path_for(name)
        log.debug("Streaming run data: %s", path)
        if not path.exists():
            raise RunDataNotFoundError(f"Run data {name!r} not found at {path}")
        return FileRunDataStream(path)

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
