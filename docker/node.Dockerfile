# Dockerfile for the MDW node image
#
# MDW uses a more minimal version of the node image
#
# IMAGE
# -----
# * <registry>/infrastructure/node-mdw:x.x.x
#

# python:3.10-slim-bookworm
# https://hub.docker.com/layers/library/python/3.10-slim-bookworm/images/sha256-6205304ead236fcdf696ab8c66e7ad91a30c84694832d414a9737743e909beb4
FROM python@sha256:6205304ead236fcdf696ab8c66e7ad91a30c84694832d414a9737743e909beb4
# For now, we are using the amd64 image manifest only. When we find an actual
# use case to support arm64 (this include algorithms), we can switch to index
# manifest.

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /vantage6

# We are still trying to reduce dependecies. Package 'vantage6' is coupled
# needlessly and pulls in a fair amount of dependecies.
COPY README.md /vantage6/README.md
COPY vantage6-common /vantage6/vantage6-common
COPY vantage6-client /vantage6/vantage6-client
COPY vantage6 /vantage6/vantage6
COPY vantage6-node /vantage6/vantage6-node

RUN pip install --upgrade pip \
    && pip install \
        -e /vantage6/vantage6-common \
        -e /vantage6/vantage6-client \
        -e /vantage6/vantage6 \
        -e /vantage6/vantage6-node
