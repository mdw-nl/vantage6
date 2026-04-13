"""
This contains the ``vnode-local`` commands. These commands are similar
to the ``v6 node`` CLI commands, but they start up the node outside of a Docker
container, and are mostly intended for development purposes.

Some commands, such as ``vnode-local start``, are used within the Docker
container when ``v6 node start`` is used.
"""

import sys

import click

import vantage6.node.globals as constants

from pathlib import Path

from vantage6 import node
from vantage6.common import error
from vantage6.common.globals import InstanceType
from vantage6.node.context import NodeContext, DockerNodeContext

from vantage6.node._version import __version__


def _load_configuration_helpers():
    try:
        from vantage6.cli.configuration_wizard import (
            configuration_wizard,
            select_configuration_questionaire,
        )
    except ModuleNotFoundError as exc:
        if exc.name == "vantage6.cli" or exc.name.startswith("vantage6.cli."):
            error(
                "Interactive node configuration requires the 'vantage6' CLI "
                "package. Install 'vantage6' or pass --config."
            )
            sys.exit(1)
        raise

    return configuration_wizard, select_configuration_questionaire


def _load_questionary():
    try:
        import questionary as q
    except ModuleNotFoundError as exc:
        if exc.name == "questionary":
            error(
                "Interactive node prompts require the 'questionary' package. "
                "Install 'questionary' or pass --config."
            )
            sys.exit(1)
        raise

    return q


@click.group(name="vnode-local")
def cli_node() -> None:
    """Command `vnode-local`."""
    pass


#
#   start
#
@cli_node.command(name="start")
@click.option("-n", "--name", default=None, help="Configuration name")
@click.option(
    "-c",
    "--config",
    default=None,
    help='Absolute path to configuration-file; overrides "name"',
)
@click.option(
    "--system",
    "system_folders",
    flag_value=True,
    help="Use configuration from system folders (default)",
)
@click.option(
    "--user",
    "system_folders",
    flag_value=False,
    default=constants.DEFAULT_NODE_SYSTEM_FOLDERS,
    help="Use configuration from user folders",
)
@click.option(
    "--dockerized/-non-dockerized",
    default=False,
    help=("Whether to use DockerNodeContext or regular NodeContext " "(default)"),
)
def cli_node_start(
    name: str, config: str, system_folders: bool, dockerized: bool
) -> None:
    """Start the node instance.

    If no name or config is specified the default.yaml configuation is used.
    In case the configuration file not exists, a questionaire is
    invoked to create one.
    """
    ContextClass = DockerNodeContext if dockerized else NodeContext

    # in case a configuration file is given, we bypass all the helper
    # stuff since you know what you are doing
    if config:
        name = Path(config).stem
        ctx = ContextClass(name, system_folders, config)

    else:
        # in case no name is supplied, ask user to select one
        if not name:
            _, select_configuration_questionaire = _load_configuration_helpers()
            name = select_configuration_questionaire(InstanceType.NODE, system_folders)

        # check that config exists in the APP, if not a questionaire will
        # be invoked
        if not ContextClass.config_exists(name, system_folders):
            question = (
                f"Configuration '{name}' does not exist.\n  Do you want to "
                "create this config now?"
            )

            if _load_questionary().confirm(question).ask():
                configuration_wizard, _ = _load_configuration_helpers()
                configuration_wizard(InstanceType.NODE, name, system_folders)

            else:
                sys.exit(0)

        # create dummy node context
        ctx = ContextClass(name, system_folders)

    # run the node application
    node.run(ctx)


#
#   version
#
@cli_node.command(name="version")
def cli_node_version() -> None:
    """Returns current version of vantage6 services installed."""
    click.echo(__version__)
