from pathlib import Path

# experimental: node discovers its own container name by using its hostname
import socket
import docker

from vantage6.common.globals import (
    PACKAGE_FOLDER,
    APPNAME
)

from vantage6.common.context import AppContext
from vantage6.common.configuration_manager import ConfigurationManager
from vantage6.cli.context import NodeContext
from vantage6.node._version import __version__


class DockerNodeContext(NodeContext):
    """Node context for the dockerized version of the node."""

    running_in_docker = True

    def __init__(self, *args, **kwargs):
        """Display node version number."""
        super().__init__(*args, **kwargs)
        self.log.info(f"Node package version '{__version__}'")

    def set_folders(self, instance_type, instance_name, system_folders):
        """ In case of the dockerized version we do not want to use user
            specified directories within the container.
        """
        dirs = self.instance_folders(
            instance_type,
            instance_name,
            system_folders
        )

        self.log_dir = dirs.get("log")
        self.data_dir = dirs.get("data")
        self.config_dir = dirs.get("config")
        self.vpn_dir = dirs.get("vpn")

    @staticmethod
    def instance_folders(instance_type, instance_name, system_folders):
        """ Log, data and config folders are always mounted. The node manager
            should take care of this.
        """
        mnt = Path("/mnt")

        return {
            "log": mnt / "log",
            "data": mnt / "data",
            "config": mnt / "config",
            "vpn": mnt / "vpn"
        }

    # experimental: node will later on use its container name to connect itself
    # to the algorithm network, but the container name can be arbitrarily set by
    # docker compose for instance. So we shouldn't assume a fixed name as
    # NodeContext's `docker_container_name()` does.
    # TODO: Does this break regular `vnode start`?
    @property
    def docker_container_name(self) -> str:
        """
        Docker container name of the node.

        Returns
        -------
        str
            Node's Docker container name
        """

        hostname = socket.gethostname()
        docker_client = docker.from_env()
        container = docker_client.containers.get(hostname)

        return container.name


class TestingConfigurationManager(ConfigurationManager):
    VALIDATORS = {}


class TestContext(AppContext):

    INST_CONFIG_MANAGER = TestingConfigurationManager
    LOGGING_ENABLED = False

    @classmethod
    def from_external_config_file(cls, path):
        return super().from_external_config_file(
            cls.test_config_location(),
            "unittest", "application", True
        )

    @staticmethod
    def test_config_location():
        return (PACKAGE_FOLDER / APPNAME /
                "_data" / "unittest_config.yaml")

    @staticmethod
    def test_data_location():
        return (PACKAGE_FOLDER / APPNAME /
                "_data")
