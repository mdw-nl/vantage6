from schema import And, Use, Optional

from vantage6.common.configuration_manager import Configuration, ConfigurationManager
from vantage6.common.node_context import NodeConfiguration, NodeConfigurationManager

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


class ServerConfiguration(Configuration):
    """
    Stores the server's configuration and defines a set of server-specific
    validators.
    """

    VALIDATORS = {
        "description": Use(str),
        "ip": Use(str),
        "port": Use(int),
        Optional("api_path"): str,
        "uri": Use(str),
        "allow_drop_all": Use(bool),
        "logging": {**LOGGING_VALIDATORS, "file": Use(str)},
        Optional("server_name"): str,
        Optional("runs_data_cleanup_days"): Use(int),
    }


class TestConfiguration(Configuration):
    VALIDATORS = {}


class ServerConfigurationManager(ConfigurationManager):
    """
    Maintains the server's configuration.

    Parameters
    ----------
    name : str
        Name of the configuration file.
    """

    def __init__(self, name, *args, **kwargs) -> None:
        super().__init__(conf_class=ServerConfiguration, name=name)

    @classmethod
    def from_file(cls, path) -> "ServerConfigurationManager":
        """
        Create a new instance of the ServerConfigurationManager from a
        configuration file.

        Parameters
        ----------
        path : str
            Path to the configuration file.

        Returns
        -------
        ServerConfigurationManager
            A new instance of the ServerConfigurationManager.
        """
        return super().from_file(path, conf_class=ServerConfiguration)


class TestingConfigurationManager(ConfigurationManager):
    def __init__(self, name, *args, **kwargs):
        super().__init__(conf_class=TestConfiguration, name=name)

    @classmethod
    def from_file(cls, path):
        return super().from_file(path, conf_class=TestConfiguration)
