import logging
import unittest

from types import SimpleNamespace
from unittest.mock import patch

from vantage6.node import Node


class TestVPNSetup(unittest.TestCase):
    def test_setup_vpn_connection_skips_manager_when_not_configured(self):
        node = Node.__new__(Node)
        node.log = logging.getLogger("test.node.vpn")
        node.config = {}

        with patch("vantage6.node.VPNManager") as vpn_manager:
            result = node.setup_vpn_connection(
                isolated_network_mgr=SimpleNamespace(),
                ctx=SimpleNamespace(),
            )

        self.assertIsNone(result)
        vpn_manager.assert_not_called()
