#!/bin/bash

set -euo pipefail

# dir where this script lives
readonly COMMON_DIR="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"

# fixed path to pre-hook script
readonly PRE_HOOK_PATH="/custom-start.d/pre_run.sh"

# default values
readonly DEFAULT_CONFIG_PATH="/mnt/config/config.yaml"
readonly DEFAULT_TEMPLATE_PATH="/mnt/config/config.yaml.j2"

# global vars
V6_CONFIG_TEMPLATE_PATH=${V6_CONFIG_TEMPLATE_PATH:-$DEFAULT_TEMPLATE_PATH}
V6_CONFIG_PATH=${V6_CONFIG_PATH:-$DEFAULT_CONFIG_PATH}


# Queries vantage6 server API (/version) every 5 seconds until it responds
# or times out (after 5 attempts with a 4 second timeout).
#
# We use this method because we know we will have python's requests module
# available, so no need to install anything else.
#
# In:
#   $1: server url API endpoint
# Out, return code:
#  0: server API endpoint is up
#  1: server API endpoint is down
# TODO: move this to a separate script?
wait_for_api_endpoint() {
    local api_endpoint_url=$1
    python - << PYTHONCODE
import sys, time, requests
url = "${api_endpoint_url}/version"
print(f"Status of API endpoint at {url} is ", end=""); sys.stdout.flush()
for i in range(5):
    try:
        if requests.get(url, timeout=4).status_code == 200:
            print(f"up!")
            sys.exit(0)
    except SystemExit as e:
        raise e
    except:
        pass
    print(".", end=""); sys.stdout.flush()
    time.sleep(5);
print("down!")
sys.exit(1)
PYTHONCODE
    return $?
}

# Template a config (yaml) file from a (j2) template. Using environment variables to defined those paths.
# Wrapper around template_config()
#
# In:
#   External env vars:
#   - MINIMAL_CONFIG_TEMPLATE_PATH: path to minimal template config file which will be used if no other template is found.
#   Env vars defined in this file:
#   - V6_CONFIG_PATH: path to config file. If defined, this funcion won't do anything.
#   - V6_CONFIG_TEMPLATE_PATH: path to template config file.
#   Arguments:
#   - $@: extra arguments to pass to template_config()
template_config_from_env() {
    # if config file exists, use it. If not, resort to config template, if not, use minimal config template.
    if [[ -f "$V6_CONFIG_PATH" ]]; then
        echo "Using config file at \"${V6_CONFIG_PATH}\""
    else
        if  [[ -f "$V6_CONFIG_TEMPLATE_PATH" ]]; then
            echo "Using template config file at \"${V6_CONFIG_TEMPLATE_PATH}\""
        else
            echo "Warning: No config file found at \"${V6_CONFIG_PATH}\" or template config file at \"${V6_CONFIG_TEMPLATE_PATH}\""
            echo "Warning: Using minimal config file at \"${MINIMAL_CONFIG_TEMPLATE_PATH}\""
            echo "Warning: This minimal config is only meant for testing purposes!"
            V6_CONFIG_TEMPLATE_PATH="${MINIMAL_CONFIG_TEMPLATE_PATH}"
        fi

        echo "Generating configuration yaml from \"${V6_CONFIG_TEMPLATE_PATH}\" and writing to \"${V6_CONFIG_PATH}\""
        template_config "${V6_CONFIG_TEMPLATE_PATH}" "${V6_CONFIG_PATH}" $@
    fi
}

# Template a config (yaml) file ($2) from a (j2) template ($1).
# Wrapper around template_config.py.
#
# In:
#  $1: template file
#  $2: final (templated) config file
#
# Out:
#   - writes file to $2
#
template_config() {
    local template=$1
    local final_config=$2
    shift 2

    # TODO: for now we are running as root within the container
    # save old umask
    old_umask=$(umask)
    umask 077

    mkdir -p $(dirname $final_config)

    # generate the config
    ${COMMON_DIR}/template_config.py $template $final_config $@

    # restore old umask
    umask $old_umask
}


# Runs a function ($1) once in the life of the container. Subsequent attempts
# to run the same function will be avoided.
#
# It's cheap way of making sure we don't try to run the same initial setup
# functions called from bootstrap scripts (run.sh) upon container restarts,
# when the read-write container layer is not deleted.
#
# In:
#  $1: function name
#
run_once_container_life() {
    local func_name=$1

    # if we've already run this function
    if [[ -f "/var/run/ran_once_${func_name}" ]]; then
        if [[ "$(cat /var/run/ran_once_${func_name})" == "finished" ]]; then
            echo "Already ran ${func_name} previously."
        else
            echo "Last time ${func_name} was interrupted it seems. Please docker rm and start again."
            exit 1
        fi
    else
        echo "starting" > /var/run/ran_once_${func_name}

        # execute function
        $func_name

        echo "finished" > /var/run/ran_once_${func_name}
    fi
}


# Runs a pre-hook script if it exists.
#
run_pre_hook() {
    if [[ -f ${PRE_HOOK_PATH} ]]; then
        echo "Sourcing pre-hook (${PRE_HOOK_PATH})"
        # We do 'source' to allow the pre-hook to override the start_server / start_node functions
        # TODO: is this too hacky for comfort?
        source ${PRE_HOOK_PATH}
    else
        echo "No pre-hook found (expected at ${PRE_HOOK_PATH})"
    fi
}
