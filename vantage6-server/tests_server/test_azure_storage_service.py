"""Tests for the Run delete cascade wiring of the Azure storage adapter."""

import unittest
from unittest.mock import patch

from sqlalchemy import inspect

from vantage6.server.model.base import Database
from vantage6.server.model.run import Run
from vantage6.server.service.azure_storage_service import AzureStorageService
from vantage6.server.service.storage_adapter import (
    StorageAdapter,
    _dispatch_run_data_delete_after_run_delete,
)

AZURE_CONFIG = {
    "container_name": "test-container",
    "connection_string": (
        "DefaultEndpointsProtocol=https;AccountName=dummyname;AccountKey=dummykey"
    ),
}


def _after_delete_listener_count() -> int:
    """Return how many after_delete listeners are attached to Run."""
    return len(inspect(Run).dispatch.after_delete)


class TestRunDeleteCascadeRegistration(unittest.TestCase):
    """The cascade must not grow as storage adapters are constructed.

    ``event.listen`` targets the mapped ``Run`` class, which outlives any
    single adapter, so a listener registered per instance is never released.
    The server builds one adapter at startup and the run-data cleanup worker
    used to build another on every hourly pass, which meant the cascade grew
    for as long as the process ran.
    """

    def setUp(self) -> None:
        Database().connect("sqlite://", allow_drop_all=True)

    def tearDown(self) -> None:
        Database().clear_data()

    def test_repeated_construction_registers_one_listener(self) -> None:
        AzureStorageService(AZURE_CONFIG)
        after_first = _after_delete_listener_count()

        for _ in range(5):
            AzureStorageService(AZURE_CONFIG)

        self.assertEqual(_after_delete_listener_count(), after_first)

    def test_incomplete_configuration_registers_nothing(self) -> None:
        before = _after_delete_listener_count()

        AzureStorageService({"container_name": "test-container"})

        self.assertEqual(_after_delete_listener_count(), before)

    def test_cascade_reaches_the_most_recent_adapter(self) -> None:
        AzureStorageService(AZURE_CONFIG)
        latest = AzureStorageService(AZURE_CONFIG)

        with patch.object(latest, "_delete_run_data_after_run_delete") as handler:
            _dispatch_run_data_delete_after_run_delete(None, None, None)

        handler.assert_called_once_with(None, None, None)

    def test_dispatch_is_a_noop_without_an_adapter(self) -> None:
        with patch.object(StorageAdapter, "_active", None):
            _dispatch_run_data_delete_after_run_delete(None, None, None)
