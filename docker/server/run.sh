#!/bin/bash

set -euo pipefail

source /vantage6/docker/common/lib.sh

readonly MINIMAL_CONFIG_TEMPLATE_PATH="/vantage6/docker/server/minimal_config.yaml.j2"
export MINIMAL_CONFIG_TEMPLATE_PATH

# Starts the server, runs it in the foreground
#
start_server() {
    # start the server
    echo "starting the server......"
    vserver-local start --config ${V6_CONFIG_PATH} -e application
}

# Calls routines to generate config file
setup_server() {
    echo "This is the first time we're upping this container"

    template_config_from_env
}

main() {
    run_once_container_life setup_server

    run_pre_hook

    echo "Starting vantage6 server"
    start_server
}

# Don't run main() if we are being sourced. This allows potential extra hacky
# development tricks in pre_run.sh that involve sourcing this file.
if [[ "${BASH_SOURCE}" == "${0}" ]]; then
    main $@
fi
