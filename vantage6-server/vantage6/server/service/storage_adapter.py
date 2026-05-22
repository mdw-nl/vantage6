"""Abstract storage adapter for the large result store.

Provides a backend-agnostic interface for storing run inputs and results
(``store_run_data`` / ``get_run_data`` / ``stream_run_data`` /
``delete_run_data``) along with a shared SQLAlchemy ``after_delete``
listener on :class:`Run` that removes the associated run data whenever
a Run row is deleted.

Concrete backends (Azure Blob Storage, local filesystem) subclass
:class:`StorageAdapter` and call ``super().__init__(config)`` only after
they are fully usable, so the listener is never registered against a
half-initialised adapter.

The module also exposes :func:`build_storage_adapter`, a small factory
that dispatches on the ``type`` field of the ``large_result_store``
configuration block.
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import IO, Iterator, Union

from sqlalchemy import event

from vantage6.common import logger_name
from vantage6.server.model.run import Run

module_name = logger_name(__name__)
log = logging.getLogger(module_name)


class RunDataStream(ABC):
    """Streaming reader for stored run data.

    The shape mirrors Azure SDK's ``StorageStreamDownloader.chunks()`` so
    the existing call site in ``blobstream.py`` works unchanged for both
    backends.
    """

    @abstractmethod
    def chunks(self) -> Iterator[bytes]:
        """Yield successive chunks of the run data's content."""


class StorageAdapter(ABC):
    """Abstract base class for large-result storage backends."""

    def __init__(self, config: dict) -> None:
        event.listen(Run, "after_delete", self._delete_run_data_after_run_delete)

    @abstractmethod
    def get_run_data(self, name: str) -> bytes:
        """Return the full content of a run-data entry as bytes.

        Raises
        ------
        FileNotFoundError
            If no entry exists for ``name``.
        """

    @abstractmethod
    def store_run_data(self, name: str, data: Union[IO, bytes]) -> None:
        """Store data under the given run-data name."""

    @abstractmethod
    def delete_run_data(self, name: str) -> None:
        """Delete a run-data entry. Must be idempotent (no error if missing)."""

    @abstractmethod
    def stream_run_data(self, name: str):
        """Return a streaming reader exposing a ``chunks()`` iterator.

        Raises
        ------
        FileNotFoundError
            If no entry exists for ``name``.
        """

    def _delete_run_data_after_run_delete(
        self, mapper, connection, target
    ) -> None:
        """Remove the associated run data when a Run row is deleted."""
        if not getattr(target, "blob_storage_used", False):
            return
        try:
            if target.result:
                self.delete_run_data(target.result)
            if target.input:
                self.delete_run_data(target.input)
        except Exception as e:
            error_msg = f"Failed to delete run data for run {target.id}: {e}"
            log.error(error_msg)
            raise RuntimeError(error_msg)


def build_storage_adapter(config: dict) -> StorageAdapter | None:
    """Build the configured storage adapter, or return ``None`` if disabled.

    Parameters
    ----------
    config : dict
        The ``large_result_store`` configuration block.

    Returns
    -------
    StorageAdapter | None
        Configured adapter, or ``None`` if the block is empty or the
        ``type`` is unknown.
    """
    if not config:
        return None

    store_type = config.get("type", "file")
    if store_type == "azure":
        from vantage6.server.service.azure_storage_service import AzureStorageService

        return AzureStorageService(config=config)
    if store_type == "file":
        from vantage6.server.service.file_storage_service import (
            DEFAULT_RUN_DATA_BASE_PATH,
            RUN_DATA_BASE_PATH_ENV_VAR,
            FileStorageService,
        )

        base_path = os.environ.get(
            RUN_DATA_BASE_PATH_ENV_VAR, DEFAULT_RUN_DATA_BASE_PATH
        )
        return FileStorageService(config=config, base_path=base_path)

    log.error(
        "Unknown large_result_store.type=%r; large result store disabled.",
        store_type,
    )
    return None
