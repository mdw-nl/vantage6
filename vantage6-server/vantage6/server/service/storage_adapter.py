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
that dispatches on the top-level ``large_run_data_store`` setting (a
string: ``"filesystem"`` or ``"azure"``). When ``"azure"`` is selected,
the Azure-specific block lives under ``azure_run_data_store``.
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


def build_storage_adapter(server_config: dict) -> StorageAdapter | None:
    """Build the configured storage adapter, or return ``None`` if disabled.

    Reads two top-level keys from the server config:

    - ``large_run_data_store`` — required string, either ``"filesystem"``
      or ``"azure"``. Absent means "disabled — use the relational DB
      for inputs and results".
    - ``azure_run_data_store`` — required when ``large_run_data_store``
      is ``"azure"``; ignored otherwise.

    Raises
    ------
    ValueError
        If the deprecated ``large_result_store`` key is present (the
        config shape changed in this release), if
        ``large_run_data_store`` is not one of the supported values,
        or if ``"azure"`` is selected without an
        ``azure_run_data_store`` block.
    """
    if "large_result_store" in server_config:
        raise ValueError(
            "Configuration key 'large_result_store' is no longer supported. "
            "Use top-level 'large_run_data_store: \"filesystem\"' or "
            "'large_run_data_store: \"azure\"' (with an 'azure_run_data_store' "
            "block for the Azure credentials). See the docs at "
            "docs/features/inter-component/blob_storage.rst."
        )

    store_type = server_config.get("large_run_data_store")
    if store_type is None:
        return None

    if store_type == "filesystem":
        from vantage6.server.service.file_storage_service import (
            DEFAULT_RUN_DATA_BASE_PATH,
            RUN_DATA_BASE_PATH_ENV_VAR,
            FileStorageService,
        )

        base_path = os.environ.get(
            RUN_DATA_BASE_PATH_ENV_VAR, DEFAULT_RUN_DATA_BASE_PATH
        )
        return FileStorageService(config={}, base_path=base_path)

    if store_type == "azure":
        azure_config = server_config.get("azure_run_data_store")
        if not azure_config:
            raise ValueError(
                "large_run_data_store is 'azure' but no 'azure_run_data_store' "
                "block was provided in the server config."
            )
        from vantage6.server.service.azure_storage_service import AzureStorageService

        return AzureStorageService(config=azure_config)

    raise ValueError(
        f"Unknown large_run_data_store={store_type!r}; expected "
        f"'filesystem' or 'azure'."
    )
