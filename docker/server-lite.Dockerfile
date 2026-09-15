# Dockerfile for the server-lite image
#
# This is a more minimal version of the server image that does not install the
# full vantage6 CLI package.
#
# IMAGE
# -----
# * <registry>/infrastructure/server-lite:x.x.x
#

# python:3.10-slim-bookworm
# https://hub.docker.com/layers/library/python/3.10-slim-bookworm/images/sha256-6205304ead236fcdf696ab8c66e7ad91a30c84694832d414a9737743e909beb4
FROM python@sha256:6205304ead236fcdf696ab8c66e7ad91a30c84694832d414a9737743e909beb4 AS uwsgi-builder
# For now, we are using the amd64 image manifest only. When we find an actual
# use case to support arm64, we can switch to an index manifest.

# Keep image layers smaller and make Python logs visible immediately in Docker.
ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

RUN apt-get update \
    && apt-get install --no-install-recommends --no-install-suggests -y \
        gcc \
        libc6-dev \
        libssl-dev \
    && rm -rf /var/lib/apt/lists/*

RUN CFLAGS="-I/usr/local/opt/openssl/include" \
        LDFLAGS="-L/usr/local/opt/openssl/lib" \
        UWSGI_PROFILE_OVERRIDE=ssl=true \
        pip wheel --wheel-dir /dist uwsgi==2.0.31

# python:3.10-slim-bookworm
# https://hub.docker.com/layers/library/python/3.10-slim-bookworm/images/sha256-6205304ead236fcdf696ab8c66e7ad91a30c84694832d414a9737743e909beb4
FROM python@sha256:6205304ead236fcdf696ab8c66e7ad91a30c84694832d414a9737743e909beb4

# Keep image layers smaller and make Python logs visible immediately in Docker.
ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /vantage6

COPY README.md /vantage6/README.md
COPY vantage6-common /vantage6/vantage6-common
COPY vantage6-backend-common /vantage6/vantage6-backend-common
COPY vantage6-server /vantage6/vantage6-server
COPY --from=uwsgi-builder /dist /dist

# The compose image uses PostgreSQL, so install the server with its PostgreSQL
# driver extra instead of relying on SQLite-only dependencies.
RUN pip install \
        -e /vantage6/vantage6-common \
        -e /vantage6/vantage6-backend-common \
        -e "/vantage6/vantage6-server[postgres]" \
    && pip install /dist/uwsgi-*.whl \
    && rm -rf /dist

# server.sh starts uWSGI on port 80.
EXPOSE 80
