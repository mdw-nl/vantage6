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
        self.name = self.docker_container_name

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
            "vpn": mnt / "vpn",
            "squid:": mnt / "squid",
            "ssh": mnt / "ssh"
        }

    # experimental: node will later on use its container name to connect itself
    # to the algorithm network, but the container name can be arbitrarily set by
    # docker compose for instance. So we shouldn't assume a fixed name as
    # NodeContext's `docker_container_name()` does.
    # TODO: Does this break regular `vnode start`?
    @property
    def docker_container_name(self) -> str:
        """
        Docker container name of the node. Unique under the same docker host.

        Returns
        -------
        str
            Node's Docker container name
        """

        hostname = socket.gethostname()
        docker_client = docker.from_env()
        container = docker_client.containers.get(hostname)

        return f"{container.name}"

    @property
    def docker_network_name(self) -> str:
        """
        Private Docker network name for this node, should be unique. Based on
        docker_container_name.

        Returns
        -------
        str
            Docker network name
        """
        return f"{self.docker_container_name}-net"

    def docker_temporary_volume_name(self, run_id: int) -> str:
        """
        Docker volume in which temporary data is stored. Temporary data is
        linked to a specific run. Multiple algorithm containers can have the
        same run id, and therefore the share same temporary volume.

        Parameters
        ----------
        run_id : int
            run id provided by the server

        Returns
        -------
        str
            Docker volume name
        """
        return f"{self.docker_container_name}-tmpvol-{run_id}"



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
