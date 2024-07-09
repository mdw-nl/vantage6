import re
import json
import hashlib
from http import HTTPStatus
import logging
import signal
import pathlib
import requests

import docker
from docker.client import DockerClient
from docker.models.containers import Container
from docker.models.volumes import Volume
from docker.models.networks import Network
from docker.utils import parse_repository_tag
from docker.auth import resolve_repository_name

from vantage6.common import logger_name
from vantage6.common.globals import APPNAME

log = logging.getLogger(logger_name(__name__))


class ContainerKillListener:
    """Listen for signals that the docker container should be shut down"""

    kill_now = False

    def __init__(self) -> None:
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, *args) -> None:
        """Set kill_now to True. This will trigger the container to stop"""
        self.kill_now = True


def check_docker_running() -> None:
    """
    Check if docker engine is running. If not, exit the program.
    """
    try:
        docker_client = docker.from_env()
        docker_client.ping()
    except Exception as exc:
        log.error(
            "Cannot reach the Docker engine! Please make sure Docker " "is running."
        )
        log.exception(exc)
        log.warning("Exiting...")
        exit(1)


def running_in_docker() -> bool:
    """
    Check if this code is executed within a Docker container.

    Returns
    -------
    bool
        True if the code is executed within a Docker container, False otherwise
    """
    return pathlib.Path("/.dockerenv").exists()


def pull_image(
    docker_client: DockerClient, image: str, suppress_error: bool = False
) -> None:
    """
    Pull a docker image

    Parameters
    ----------
    docker_client: DockerClient
        A Docker client
    image: str
        Name of the image to pull
    suppress_error: bool
        Whether to suppress the error if the image could not be pulled

    Raises
    ------
    docker.errors.APIError
        If the image could not be pulled
    """
    try:
        docker_client.images.pull(image)
        log.debug("Succeeded to pull image %s", image)
    except docker.errors.APIError as exc:
        if not suppress_error:
            log.error("Failed to pull image! %s", image)
            log.exception(exc)
        raise docker.errors.APIError("Failed to pull image") from exc


def get_container(docker_client: DockerClient, **filters) -> Container:
    """
    Return container if it exists after searching using kwargs

    Parameters
    ----------
    docker_client: DockerClient
        Python docker client
    **filters:
        These are arguments that will be passed to the client.container.list()
        function. They should yield 0 or 1 containers as result (e.g.
        name='something')

    Returns
    -------
    Container or None
        Container if it exists, else None
    """
    running_containers = docker_client.containers.list(all=True, filters=filters)
    return running_containers[0] if running_containers else None


def remove_container_if_exists(docker_client: DockerClient, **filters) -> None:
    """
    Kill and remove a docker container if it exists

    Parameters
    ----------
    docker_client: DockerClient
        A Docker client
    **filters:
        These are arguments that will be passed to the client.container.list()
        function. They should yield 0 or 1 containers as result (e.g.
        name='something')
    """
    container = get_container(docker_client, **filters)
    if container:
        log.warn("Removing container that was already running: " f"{container.name}")
        remove_container(container, kill=True)


def remove_container(container: Container, kill: bool = False) -> None:
    """
    Removes a docker container

    Parameters
    ----------
    container: Container
        The container that should be removed
    kill: bool
        Whether or not container should be killed before it is removed
    """
    try:
        container.remove(force=kill)
    except Exception as e:
        log.exception(f"Failed to remove container {container.name}")
        log.exception(e)


def stop_container(container: Container, force: bool = False):
    """
    Stop a docker container

    Parameters
    ----------
    container: Container
        The container that should be stopped
    force: bool
        Whether to kill the container or if not, try to stop it gently
    """
    if force:
        container.kill()
    else:
        container.stop()


def get_network(docker_client: DockerClient, **filters) -> Network:
    """Return network if it exists after searching using kwargs

    Parameters
    ----------
    docker_client: DockerClient
        Python docker client
    **filters:
        These are arguments that will be passed to the client.network.list()
        function. They should yield 0 or 1 networks as result (e.g.
        name='something')

    Returns
    -------
    Container or None
        Container if it exists, else None
    """
    networks = docker_client.networks.list(filters=filters)
    return networks[0] if networks else None


def delete_network(network: Network, kill_containers: bool = True) -> None:
    """Delete network and optionally its containers

    Parameters
    ----------
    network: Network
        Network to delete
    kill_containers: bool
        Whether to kill the containers in the network (otherwise they are
        merely disconnected)
    """
    if not network:
        log.warn("Network not defined! Not removing anything, continuing...")
        return
    network.reload()
    for container in network.containers:
        log.info(f"Removing container {container.name} in old network")
        if kill_containers:
            log.warn(f"Killing container {container.name}")
            remove_container(container, kill=True)
        else:
            network.disconnect(container)
    # remove the network
    try:
        network.remove()
    except Exception:
        log.warn(f"Could not delete existing network {network.name}")


def get_networks_of_container(container: Container) -> dict:
    """
    Get list of networks the container is in

    Parameters
    ----------
    container: Container
        The container in which we are interested

    Returns
    -------
    dict
        Describes container's networks and their properties
    """
    container.reload()
    return container.attrs["NetworkSettings"]["Networks"]


def get_num_nonempty_networks(container: Container) -> int:
    """
    Get number of networks the container is in where it is not the only one

    Parameters
    ----------
    container: Container
        The container in which we are interested

    Returns
    -------
    int
        Number of networks in which the container resides in which there are
        also other containers
    """
    count_non_empty_networks = 0
    docker_client = docker.from_env()

    networks = get_networks_of_container(container)
    for network_properties in networks.values():
        network_obj = docker_client.networks.get(network_properties["NetworkID"])
        if not network_obj:
            continue
        containers = network_obj.attrs["Containers"]
        if len(containers) > 1:
            count_non_empty_networks += 1
    return count_non_empty_networks


def get_server_config_name(container_name: str, scope: str) -> str:
    """
    Get the configuration name of a server from its docker container name

    Docker container name of the server is formatted as
    f"{APPNAME}-{self.name}-{self.scope}-server". This will return {self.name}

    Parameters
    ----------
    container_name: str
        Name of the docker container in which the server is running
    scope: str
        Scope of the server (e.g. 'system' or 'user')

    Returns
    -------
    str
        A server's configuration name
    """
    idx_scope = container_name.rfind(scope)
    length_app_name = len(APPNAME)
    return container_name[length_app_name + 1 : idx_scope - 1]


def delete_volume_if_exists(client: docker.DockerClient, volume_name: Volume) -> None:
    """
    Delete a volume if it exists

    Parameters
    ----------
    client: docker.DockerClient
        Docker client
    volume: Volume
        Volume to delete
    """
    try:
        volume = client.volumes.get(volume_name)
        if volume:
            volume.remove()
    except (docker.errors.NotFound, docker.errors.APIError):
        log.warning("Could not delete volume %s", volume_name)


def parse_image_name(image: str) -> tuple[str, str, str]:
    """
    Parse image name into registry, repository, tag

    Parameters
    ----------
    image: str
        Image name. E.g. "harbor2.vantage6.ai/algorithms/average:latest" or
        "library/hello-world"

    Returns
    -------
    tuple[str, str, str]
        Registry, repository, and tag. Tag is "latest" if not specified in 'image'
    """
    registry_repository, tag = parse_repository_tag(image)
    tag = tag or "latest"
    registry, repository = resolve_repository_name(registry_repository)
    return registry, repository, tag


def get_manifest(
    registry: str,
    image: str,
    tag: str,
) -> dict:
    """
    Get the manifest of an image

    This uses the OCI distribution specification which is supported by all major
    container registries.

    Parameters
    ----------
    registry: str
        The registry of the image, e.g. "harbor2.vantage6.ai" for image
        "harbor2.vantage6.ai/demo/average:latest"
    image: str
        The image name without the registry, e.g. "demo/average" for image
        "harbor2.vantage6.ai/demo/average:latest"
    tag: str
        The tag of the image, e.g. "latest" for image
        "harbor2.vantage6.ai/demo/average:latest"

    Returns
    -------
    requests.Response
        Response containing the manifest of the image

    Raises
    ------
    ValueError
        If the image name is invalid
    """
    # if requesting from docker hub, manifests are at 'registry-1.docker.io'
    if registry == "docker.io":
        registry = "registry-1.docker.io"

    # request manifest. First try without authentication, as that is the most common
    # case. If that fails, try with authentication
    headers = {"Accept": "application/vnd.docker.distribution.manifest.v2+json"}
    manifest_endpoint = f"https://{registry}/v2/{image}/manifests/{tag}"
    response = requests.get(manifest_endpoint, headers=headers, timeout=60)

    # try requesting manifest using authentication from 'www-authenticate' header if
    # anonymous request failed. This has been tested with DockerHub and Github container
    # registry
    if (
        response.status_code == HTTPStatus.UNAUTHORIZED
        and "www-authenticate" in response.headers
    ):
        realm_pattern = r'Bearer realm="(?P<realm>[^"]+)"'
        scope_pattern = r'scope="(?P<scope>[^"]+)"'
        service_pattern = r'service="(?P<service>[^"]+)"'
        realm_match = re.match(realm_pattern, response.headers["www-authenticate"])
        scope_match = re.search(scope_pattern, response.headers["www-authenticate"])
        service_match = re.search(service_pattern, response.headers["www-authenticate"])
        if realm_match and scope_match and service_match:
            token_response = requests.get(
                realm_match.group("realm"),
                params={
                    "scope": scope_match.group("scope"),
                    "service": service_match.group("service"),
                },
                timeout=60,
            )
            if token_response.status_code == HTTPStatus.OK:
                token = token_response.json()["token"]
                response = requests.get(
                    manifest_endpoint,
                    headers={"Authorization": f"Bearer {token}", **headers},
                    timeout=60,
                )

    # TODO add support for private images (where we need to really login with a user
    # and password). The following code works on private harbor images, but may not
    # work elsewhere. It is commented out for now as it is not
    # properly tested and never used anyway.
    # response = requests.get(
    #     manifest_endpoint,
    #     auth=HTTPBasicAuth(registry_user, registry_password),
    #     timeout=60,
    # )

    # handle errors or return manifest
    if response.status_code == HTTPStatus.NOT_FOUND:
        raise ValueError(f"Image {image}:{tag} from registry {registry} not found!")
    elif response.status_code != HTTPStatus.OK:
        raise ValueError(
            "Could not retrieve image manifest from "
            f"https://{registry}/v2/{image}/manifests/{tag}"
        )
    return response


def get_digest(full_image: str) -> str:
    """
    Get digest of an image

    Parameters
    ----------
    full_image: str
        Image name. E.g. "harbor2.vantage6.ai/algorithms/average:latest"

    Returns
    -------
    str
        Digest of the image
    """
    registry, img, tag = parse_image_name(full_image)
    manifest_response = get_manifest(registry, img, tag)
    if "Docker-Content-Digest" in manifest_response.headers:
        return manifest_response.headers["Docker-Content-Digest"]
    else:
        return __calculate_digest(manifest_response.json())


def __calculate_digest(manifest: str) -> str:
    """
    Calculate the SHA256 digest from a Docker image manifest.

    Parameters
    ----------
    manifest : str
        Docker image manifest

    Returns
    -------
    str
        SHA256 digest of the manifest
    """
    # Serialize the manifest using canonical JSON
    serialized_manifest = json.dumps(
        manifest,
        indent=3,  # Believe it or not, this spacing is required to get the right SHA
    ).encode("utf-8")
    # Calculate the SHA256 digest
    digest = hashlib.sha256(serialized_manifest).hexdigest()
    return f"sha256:{digest}"
