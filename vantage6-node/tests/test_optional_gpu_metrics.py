import logging
import unittest

from unittest.mock import patch

from vantage6.node import Node


class TestOptionalGpuMetrics(unittest.TestCase):
    def test_gpu_metadata_requires_optional_nvidia_ml_py(self):
        node = Node.__new__(Node)
        node.log = logging.getLogger("test.node.optional_gpu_metrics")
        node.gpu_metadata_available = True

        with patch(
            "vantage6.node.importlib.import_module",
            side_effect=ModuleNotFoundError("No module named 'pynvml'"),
        ):
            with self.assertRaisesRegex(RuntimeError, "nvidia-ml-py"):
                node._Node__gather_gpu_metadata()

        self.assertFalse(node.gpu_metadata_available)
