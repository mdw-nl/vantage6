from __future__ import annotations

import os
from pathlib import Path

from schema import And, Optional, Or, Use

from vantage6.common._version import __version__
from vantage6.common.configuration_manager import Configuration, ConfigurationManager
from vantage6.common.context import AppContext
from vantage6.common.globals import APPNAME, InstanceType


# This default is still duplicated in the CLI and node packages while we
# decouple node config/context ownership from the CLI package.
DEFAULT_NODE_SYSTEM_FOLDERS = False

LOGGING_VALIDATORS = {
    "level": And(
        Use(str), lambda lvl: lvl in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
    ),
    "use_console": Use(bool),
    "backup_count": And(Use(int), lambda n: n > 0),
    "max_size": And(Use(int), lambda b: b > 16),
    "format": Use(str),
    "datefmt": Use(str),
}


class NodeConfiguration(Configuration):
    """
    Stores the node's configuration and defines a set of node-specific
    validators.
    """

    VALIDATORS = {
        "api_key": Use(str),
        "server_url": Use(str),
        "port": Or(Use(int), None),
        "task_dir": Use(str),
        # TODO: remove `dict` validation from databases
        "databases": Or([Use(dict)], dict, None),
        "api_path": Use(str),
        "logging": LOGGING_VALIDATORS,
        "encryption": {"enabled": bool, Optional("private_key"): Use(str)},
        Optional("node_extra_env"): dict,
        Optional("node_extra_mounts"): [str],
        Optional("node_extra_hosts"): dict,
        Optional("share_algorithm_logs"): Use(bool),
    }


class NodeConfigurationManager(ConfigurationManager):
    """
    Maintains the node's configuration.

    Parameters
    ----------
    name : str
        Name of the configuration file.
    """

    def __init__(self, name, *args, **kwargs) -> None:
        super().__init__(conf_class=NodeConfiguration, name=name)

    @classmethod
    def from_file(cls, path: str) -> "NodeConfigurationManager":
        """
        Create a new instance of the NodeConfigurationManager from a
        configuration file.

        Parameters
        ----------
        path : str
            Path to the configuration file.

        Returns
        -------
        NodeConfigurationManager
            A new instance of the NodeConfigurationManager.
        """
        return super().from_file(path, conf_class=NodeConfiguration)


class NodeContext(AppContext):
    """
    Node context object for the host system.

    See DockerNodeContext for the node instance mounts when running as a
    dockerized service.
    """

    INST_CONFIG_MANAGER = NodeConfigurationManager

    def __init__(
        self,
        instance_name: str,
        system_folders: bool = DEFAULT_NODE_SYSTEM_FOLDERS,
        config_file: str | None = None,
        print_log_header: bool = True,
    ):
        """
        Create a new node context for a host-side node instance.

        Parameters
        ----------
        instance_name : str
            Name of the configuration instance, corresponding to the
            configuration filename.
        system_folders : bool, optional
            Whether we use the system-wide configuration folders instead of the
            user-specific ones.
        config_file : str, optional
            Explicit path to a configuration file. If omitted, we resolve the
            config file from the standard node configuration folders.
        print_log_header : bool, optional
            Whether we write the startup banner to the configured log.
        """
        super().__init__(
            InstanceType.NODE,
            instance_name,
            system_folders,
            config_file,
            print_log_header,
        )
        if print_log_header:
            self.log.info("vantage6 version '%s'", __version__)

    @classmethod
    def from_external_config_file(
        cls, path: str, system_folders: bool = DEFAULT_NODE_SYSTEM_FOLDERS
    ) -> NodeContext:
        """
        Create a node context from an external configuration file. External
        means that the configuration file is not located in the default folders
        but its location is specified by the user.

        Parameters
        ----------
        path : str
            Path of the configuration file.
        system_folders : bool, optional
            Whether we use the system-wide configuration folders instead of the
            user-specific ones.

        Returns
        -------
        NodeContext
            Node context object.
        """
        return super().from_external_config_file(
            Path(path).resolve(), InstanceType.NODE, system_folders
        )

    @classmethod
    def config_exists(
        cls,
        instance_name: str,
        system_folders: bool = DEFAULT_NODE_SYSTEM_FOLDERS,
    ) -> bool:
        """
        Check if a configuration file exists.

        Parameters
        ----------
        instance_name : str
            Name of the configuration instance, corresponding to the
            configuration filename.
        system_folders : bool, optional
            Whether we use the system-wide configuration folders instead of the
            user-specific ones.

        Returns
        -------
        bool
            Whether the configuration file exists.
        """
        return super().config_exists(
            InstanceType.NODE, instance_name, system_folders=system_folders
        )

    @classmethod
    def available_configurations(
        cls, system_folders: bool = DEFAULT_NODE_SYSTEM_FOLDERS
    ) -> tuple[list, list]:
        """
        Find all available node configurations in the default folders.

        Parameters
        ----------
        system_folders : bool, optional
            Whether we search the system-wide configuration folders instead of
            the user-specific ones.

        Returns
        -------
        tuple[list, list]
            The first list contains validated configuration files, and the
            second list contains invalid configuration files.
        """
        return super().available_configurations(InstanceType.NODE, system_folders)

    @staticmethod
    def type_data_folder(
        system_folders: bool = DEFAULT_NODE_SYSTEM_FOLDERS,
    ) -> Path:
        """
        Obtain OS specific data folder where to store node specific data.

        Parameters
        ----------
        system_folders : bool, optional
            Whether we use the system-wide configuration folders instead of the
            user-specific ones.

        Returns
        -------
        Path
            Path to the data folder.
        """
        return AppContext.type_data_folder(InstanceType.NODE.value, system_folders)

    @property
    def databases(self) -> dict:
        """
        Dictionary of local databases that are available for this node.

        Returns
        -------
        dict
            Dictionary with database names as keys and their corresponding
            values from the node configuration.
        """
        return self.config["databases"]

    @property
    def docker_container_name(self) -> str:
        """
        Docker container name of the node.

        Returns
        -------
        str
            Node Docker container name.
        """
        return f"{APPNAME}-{self.name}-{self.scope}"

    @property
    def docker_network_name(self) -> str:
        """
        Private Docker network name which is unique for this node.

        Returns
        -------
        str
            Docker network name.
        """
        return f"{APPNAME}-{self.name}-{self.scope}-net"

    @property
    def docker_volume_name(self) -> str:
        """
        Docker volume in which task data is stored. If we use a file-based
        database, this volume also contains the database file.

        Returns
        -------
        str
            Docker volume name.
        """
        return os.environ.get("DATA_VOLUME_NAME", f"{self.docker_container_name}-vol")

    @property
    def docker_vpn_volume_name(self) -> str:
        """
        Docker volume in which the VPN configuration is stored.

        Returns
        -------
        str
            Docker volume name.
        """
        return os.environ.get(
            "VPN_VOLUME_NAME", f"{self.docker_container_name}-vpn-vol"
        )

    @property
    def docker_ssh_volume_name(self) -> str:
        """
        Docker volume in which the SSH configuration is stored.

        Returns
        -------
        str
            Docker volume name.
        """
        return os.environ.get(
            "SSH_TUNNEL_VOLUME_NAME", f"{self.docker_container_name}-ssh-vol"
        )

    @property
    def docker_squid_volume_name(self) -> str:
        """
        Docker volume in which the squid configuration is stored.

        Returns
        -------
        str
            Docker volume name.
        """
        return os.environ.get(
            "SSH_SQUID_VOLUME_NAME", f"{self.docker_container_name}-squid-vol"
        )

    @property
    def proxy_log_file(self):
        return self.log_file_name(type_="proxy_server")

    def docker_temporary_volume_name(self, job_id: int) -> str:
        """
        Docker volume in which temporary data is stored. Temporary data is
        linked to a specific run, so multiple algorithm containers can share
        the same temporary volume for the same run.

        Parameters
        ----------
        job_id : int
            Run id provided by the server.

        Returns
        -------
        str
            Docker volume name.
        """
        return f"{APPNAME}-{self.name}-{self.scope}-{job_id}-tmpvol"

    def get_database_uri(self, label: str = "default") -> str:
        """
        Obtain the database URI for a specific database.

        Parameters
        ----------
        label : str, optional
            Database label, by default ``"default"``.

        Returns
        -------
        str
            URI to the database.
        """
        return self.config["databases"][label]
