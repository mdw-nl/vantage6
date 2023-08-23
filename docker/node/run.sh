#!/bin/bash

set -euo pipefail

# Global vars
# Will contain databases.yaml.j2 and file-based databases
V6_NODE_DATABASES_DIR="/mnt/databases"

# In a dockerized node, these paths are harcoded here:
#  vantage6/vantage6-node/vantage6/node/context.py::DockerNodeContext:instance_folders
readonly V6_NODE_DIR_DATA=${V6_NODE_DIR_DATA:-"/mnt/data"}
readonly V6_NODE_DIR_LOG=${V6_NODE_DIR_LOG:-"/mnt/log"}
readonly V6_NODE_DIR_VPN=${V6_NODE_DIR_VPN:-"/mnt/vpn"}
readonly V6_NODE_DIR_SSH=${V6_NODE_DIR_SSH:-"/mnt/ssh"}
readonly V6_NODE_DIR_SQUID=${V6_NODE_DIR_SQUID:-"/mnt/squid"}

source /vantage6/docker/common/lib.sh

readonly MINIMAL_CONFIG_TEMPLATE_PATH="/vantage6/docker/node/minimal_config.yaml.j2"

# we export so template config code can read them
export MINIMAL_CONFIG_TEMPLATE_PATH
export V6_NODE_DIR_DATA


# Different ways of configure a node:
# 1. Providing a template config file
# 2. Providing a config file
# 3. Using a built-in template config file


# Starts the node, runs it on the foreground
start_node() {
    vnode-local start --config ${V6_CONFIG_PATH} --dockerized -e application
}

setup_node() {
    # create expected directories if they don't already exist (volume mounts?)
    # TODO: but the definition of these should come form a central place... not
    # from above.. pending refactor of docker volumes and dockerized vs
    # non-dockerized
    mkdir -p ${V6_NODE_DIR_DATA} ${V6_NODE_DIR_LOG} ${V6_NODE_DIR_VPN} ${V6_NODE_DIR_SSH} ${V6_NODE_DIR_SQUID}

    # TODO: Maybe, if the user hasn't provided docker volume names for the
    # above, we just create them and mount them at the default locations wihin
    # the container.  I'm assuming here that we mount them (node), write
    # whatever we need to (config/data) and create containers (vpn, squid,
    # algo..) that will use them.

    template_config_from_env --extra-dirs ${V6_NODE_DATABASES_DIR}
}

main() {
    # wait for server to be up
    wait_for_api_endpoint "$V6_SERVER_URL:$V6_SERVER_PORT/$V6_API_PATH" || { echo "server not up"; exit 1; }

    # set up
    run_once_container_life setup_node

    echo "Reading databases config and setting appropriate env vars for dockerzied node"
    # printing out for debugging
    echo "DEBUG: "
    /vantage6/docker/node/print_databases_env_exports.py
    eval $(/vantage6/docker/node/print_databases_env_exports.py)

    run_pre_hook

    echo "Starting node"
    start_node
}

main
