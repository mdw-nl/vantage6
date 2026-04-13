import logging
import unittest

from unittest.mock import patch

from vantage6.node.docker.docker_manager import DockerManager


class TestOptionalAlgorithmTools(unittest.TestCase):
    def test_get_column_names_requires_optional_algorithm_tools(self):
        manager = DockerManager.__new__(DockerManager)
        manager.log = logging.getLogger("test.node.optional_algorithm_tools")
        manager.databases = {
            "default": {
                "is_file": True,
                "type": "csv",
                "uri": "/mnt/default.csv",
            }
        }

        with patch(
            "vantage6.node.docker.docker_manager.importlib.import_module",
            side_effect=ModuleNotFoundError(
                "No module named 'vantage6.algorithm.tools.wrappers'"
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "vantage6-algorithm-tools"
            ):
                manager.get_column_names("default", "csv")
