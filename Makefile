# `make` is expected to be called from the directory that contains
# this Makefile

# docker image tag
TAG ?= petronas
REGISTRY ?= harbor2.vantage6.ai

# infrastructure base image version
BASE ?= 3

help:
	@echo "Available commands to 'make':"
	@echo "  set-version          : set version (e.g set-version FLAGS=\"--version 2.0.0 --build 0 --spec alpha\")"
	@echo "  uninstall            : uninstall all vantage6 packages"
	@echo "  install              : do a regular install of all vantage6 packages"
	@echo "  install-dev          : do an editable install of all vantage6 packages"
	@echo "  image                : build the node/server docker image"
	@echo "  base-image           : build the infrastructure base image"
	@echo "  algorithm-base-image : build the algorithm base image"
	@echo "  support-image        : build the supporing images"
	@echo "  rebuild              : rebuild all python packages"
	@echo "  publish              : publish built python packages to pypi.org (BE CAREFUL!)"
	@echo "  community            : notify community FLAGS="--version 99.99.88 --notes 'I should have done more!' --post-notes 'Oh.. Maybe not'""
	@echo "  test                 : run all unittests and compute coverage"
	@echo "  devdocs              : run a documentation development server"
	@echo ""
	@echo "Using "
	@echo "  tag:      ${TAG}"
	@echo "  registry: ${REGISTRY}"
	@echo "  base:     ${BASE}"

set-version:
	# --version --build --spec --post
	cd tools && ls
	cd tools && python update-version.py ${FLAGS}

community:
	#  make community FLAGS="--version 99.99.88 --notes 'I should have done more!' --post-notes 'Oh.. Maybe not'"
	cd tools && python update-discord.py ${FLAGS}

uninstall:
	pip uninstall -y vantage6
	pip uninstall -y vantage6-client
	pip uninstall -y vantage6-common
	pip uninstall -y vantage6-node
	pip uninstall -y vantage6-server

install:
	cd vantage6-common && pip install .
	cd vantage6-client && pip install .
	cd vantage6 && pip install .
	cd vantage6-node && pip install .
	cd vantage6-server && pip install .

install-dev:
	cd vantage6-common && pip install -e .
	cd vantage6-client && pip install -e .
	cd vantage6 && pip install -e .[dev]
	cd vantage6-node && pip install -e .[dev]
	cd vantage6-server && pip install -e .[dev]

base-image:
	@echo "Building ${REGISTRY}/infrastructure/infrastructure-base:${TAG}"
	@echo "Building ${REGISTRY}/infrastructure/infrastructure-base:latest"
	docker buildx build \
		--tag ${REGISTRY}/infrastructure/infrastructure-base:${TAG} \
		--tag ${REGISTRY}/infrastructure/infrastructure-base:latest \
		--platform linux/arm64,linux/amd64 \
		-f ./docker/infrastructure-base.Dockerfile \
		--push .

algorithm-base-image:
	@echo "Building ${REGISTRY}/algorithms/algorithm-base:${TAG}"
	docker buildx build \
		--tag ${REGISTRY}/infrastructure/algorithm-base:${TAG} \
		--tag ${REGISTRY}/infrastructure/algorithm-base:latest \
		--platform linux/arm64,linux/amd64 \
		-f ./docker/algorithm-base.Dockerfile \
		--push .

support-image:
	@echo "Building support images"
	@echo "All support images are also tagged with `latest`"
	make support-alpine-image
	make support-vpn-client-image
	make support-vpn-configurator-image
	make support-ssh-tunnel-image
	make support-squid-image

support-squid-image:
	@echo "Building ${REGISTRY}/infrastructure/squid:${TAG}"
	docker buildx build \
		--tag ${REGISTRY}/infrastructure/squid:${TAG} \
		--tag ${REGISTRY}/infrastructure/squid:latest \
		--platform linux/arm64,linux/amd64 \
		-f ./docker/squid.Dockerfile \
		--push .

support-alpine-image:
	@echo "Building ${REGISTRY}/infrastructure/alpine:${TAG}"
	docker buildx build \
		--tag ${REGISTRY}/infrastructure/alpine:${TAG} \
		--tag ${REGISTRY}/infrastructure/alpine:latest \
		--platform linux/arm64,linux/amd64 \
		-f ./docker/alpine.Dockerfile \
		--push .

support-vpn-client-image:
	@echo "Building ${REGISTRY}/infrastructure/vpn-client:${TAG}"
	docker buildx build \
		--tag ${REGISTRY}/infrastructure/vpn-client:${TAG} \
		--tag ${REGISTRY}/infrastructure/vpn-client:latest \
		--platform linux/arm64,linux/amd64 \
		-f ./docker/vpn-client.Dockerfile \
		--push .

support-vpn-configurator-image:
	@echo "Building ${REGISTRY}/infrastructure/vpn-configurator:${TAG}"
	docker buildx build \
		--tag ${REGISTRY}/infrastructure/vpn-configurator:${TAG} \
		--tag ${REGISTRY}/infrastructure/vpn-configurator:latest \
		--platform linux/arm64,linux/amd64 \
		-f ./docker/vpn-configurator.Dockerfile \
		--push .

support-ssh-tunnel-image:
	@echo "Building ${REGISTRY}/infrastructure/ssh-tunnel:${TAG}"
	docker buildx build \
		--tag ${REGISTRY}/infrastructure/ssh-tunnel:${TAG} \
		--tag ${REGISTRY}/infrastructure/ssh-tunnel:latest \
		--platform linux/arm64,linux/amd64 \
		-f ./docker/ssh-tunnel.Dockerfile \
		--push .

image:
	@echo "Building ${REGISTRY}/infrastructure/node:${TAG}"
	@echo "Building ${REGISTRY}/infrastructure/server:${TAG}"
	docker buildx build \
		--tag ${REGISTRY}/infrastructure/node:${TAG} \
		--tag ${REGISTRY}/infrastructure/server:${TAG} \
		--build-arg TAG=${TAG} \
		--build-arg BASE=${BASE} \
		--platform linux/arm64,linux/amd64 \
		-f ./docker/node-and-server.Dockerfile \
		--push .

# Draft: dockerized images.
#        * For now, only building for amd64 with default builder as that seems
#        quicker (during development) than dealing with a 'docker-container'
#        builder
#        * nofile limit is set in case container where this is built has a very
#        high nofile limit. On which pyhton 2.7's Popen() will get stuck, as it tries to
#        close all file descriptors...
dockerized: dockerized-server dockerized-node

dockerized-base-image:
	@echo "Building ${REGISTRY}/infrastructure/dockerized-infrastructure-base:${TAG}"
	@echo "Building ${REGISTRY}/infrastructure/dockerized-infrastructure-base:latest"
	docker buildx build \
		--tag ${REGISTRY}/infrastructure/dockerized-infrastructure-base:${TAG} \
		--tag ${REGISTRY}/infrastructure/dockerized-infrastructure-base:latest \
		--tag ${REGISTRY}/infrastructure/dockerized-infrastructure-base:${BASE} \
		--platform linux/amd64 \
		--ulimit nofile=262144:262144 \
		--load \
		-f ./docker/dockerized-infrastructure-base.Dockerfile .

dockerized-server: dockerized-base-image
	@echo "Building ${REGISTRY}/infrastructure/dockerized-server:${TAG}"
	docker buildx build \
		--tag ${REGISTRY}/infrastructure/dockerized-server:${TAG} \
		--tag ${REGISTRY}/infrastructure/dockerized-server:latest \
		--build-arg TAG=${TAG} \
		--build-arg BASE=${BASE} \
		--platform linux/amd64 \
		--ulimit nofile=262144:262144 \
		--load \
		-f ./docker/dockerized-server.Dockerfile .

dockerized-node: dockerized-base-image
	@echo "Building ${REGISTRY}/infrastructure/dockerized-node:${TAG}"
	docker buildx build \
		--tag ${REGISTRY}/infrastructure/dockerized-node:${TAG} \
		--tag ${REGISTRY}/infrastructure/dockerized-node:latest \
		--build-arg TAG=${TAG} \
		--build-arg BASE=${BASE} \
		--platform linux/amd64 \
		--ulimit nofile=262144:262144 \
		--load \
		-f ./docker/dockerized-node.Dockerfile .

rebuild:
	@echo "------------------------------------"
	@echo "         BUILDING PROJECT           "
	@echo "------------------------------------"
	@echo "------------------------------------"
	@echo "         VANTAGE6 COMMON            "
	@echo "------------------------------------"
	cd vantage6-common && make rebuild
	@echo "------------------------------------"
	@echo "         VANTAGE6 CLIENT            "
	@echo "------------------------------------"
	cd vantage6-client && make rebuild
	@echo "------------------------------------"
	@echo "         VANTAGE6 CLI            "
	@echo "------------------------------------"
	cd vantage6 && make rebuild
	@echo "------------------------------------"
	@echo "         VANTAGE6 NODE            "
	@echo "------------------------------------"
	cd vantage6-node && make rebuild
	@echo "------------------------------------"
	@echo "         VANTAGE6 SERVER            "
	@echo "------------------------------------"
	cd vantage6-server && make rebuild

publish:
	cd vantage6-common && make publish
	cd vantage6-client && make publish
	cd vantage6 && make publish
	cd vantage6-node && make publish
	cd vantage6-server && make publish

test:
	coverage run --source=vantage6 --omit="utest.py","*.html","*.htm","*.txt","*.yml","*.yaml" utest.py

devdocs:
	sphinx-autobuild docs docs/_build/html --watch .
