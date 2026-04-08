# Dockerfile for the node image
#
# IMAGE
# -----
# * <registry>/infrastructure/node-lite:x.x.x
#
#
# TODO: pin this
FROM python:3.10-slim-bookworm

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
