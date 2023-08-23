What's implemented is just a proof of concept, not a proposal.

For example, it might be better to re-write those start up scripts into python, etc. But we should probably first decide on which design direction to go.

## Design Options

A few options that I see are the following.

#### Option: Minimally invasive 

Modify existing code and behavior as little as possible, but enough to let a user use run a dockerized node comfortably. To some degree, this is what is currenly quikcy implemeneted in this proof-of-concept..

#### Option: Abandon vnode cli as the primary way

So as to make it simpler and only have to worry about maintaining one way of doing things, a more drastic option would be abandoning the current vnode cli that uses docker-py to set up the environment for a dockerized node, in favor of docker compose.

Some vnode commands would have clear alternatives:

| vnode cli command | alternative |
|-------------------|-------------|
| list    | specifed in docker-compose.yml, online status via 'docker compose ps'
| start   | docker compose up node-name |
| stop    | docker compose stop node-name |
| attach  | docker compose logs node-name |

`create-private-key`, `new`, and `set-api-key` could be:
* shipped as a standalone python application for those interested
* or ship that standalone application in an image and use it with something like:
  ```
  $ docker run --rm -v ~/.config/vantage6/:/root/.config/vantage6 vantage6/utils new
  ```
* or shipped within the node an use with something like
  ```
  $ docker run --rm -v ~/.config/vantage6/:/root/.config/vantage6 vantage6/node new
  ```
  Perhaps new could spit out an initial docker-compose.yml

`clean` and `remove`: we would have to think if this makes sense to keep and where


## Relevant refactor ideas

It might be necessary or convienient to refactor some of the code to have this "dockerization" be more straightforward. 

### No dockerized assumtions

As a design principle, it might be nice (why?) to allow for the application to run outside of a docker container. And to make no assumptions as to where it is running, just that it's running on a linux machine. Dockerization of the application would be an extra layer (start-up scripts (entrypoint) and docker-compose).

Ultimatley vantage6 does depend on docker (to run algorithms in a restricted environment), but that is a different story.

At the moment there is a distiction between a dockerzied node and a non-dockerized node. In dockerized node paths are always expected at '/mnt', file databases are dealt with differently, etc. Perhaps we can always let the user choose the different paths, but have sensible defaults.

For example, configuarion is by default expected at /etc/vantage6/config.yml. But if the user runs it with a different option (or via an env var), then we read it from there.

### Docker volumes

Named docker volumes are now used to shared data between the host, the node, and {the algorithm, vpn conatiner, squid proxy container, ssh tunnel containers, ..}. 

The paths where these docker volumes are mounted could be configured too, defaulting to sensible settings.

When the application runs (whether it's inside a docker container or not), it can look check if the name for the different docker volume is given and use that (to write config file or whathaveya). If they aren't found, it could create them. This is similar to how it is done now, but outside of cli vnode.

Alternatively, are there better alternatives that named docker volumes here? Bind mount from the rw-layer woundn't work probably, ... (my TODO: understand this fully ..)


### Configuration

In this PoC, config is handled with a template. The user can volume-map in a config file (yaml), or a template (.j2) or nothing (and a default template will be used). The template is a temporary solution so the user can:
* Provide secrets via docker secrets: 
* Re-use configuration for different nodes: differences are achived via env vars
* Have a default config: allowing for essential config options such as server_url via env vars

But templating a yaml file does not feel robust... And dealing with the databases section template at the moment is rather hacky.
