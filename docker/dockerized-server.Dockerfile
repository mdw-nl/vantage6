# Dockerfile for the server image
#
# IMAGES
# ------
# * harbor2.vantage6.ai/infrastructure/dockerized-server:x.x.x
#
ARG TAG=latest
ARG BASE=3
FROM harbor2.vantage6.ai/infrastructure/dockerized-infrastructure-base:${BASE}

LABEL version=${TAG}
LABEL maintainer="Frank Martin <f.martin@iknl.nl>"

# copy sources
COPY vantage6-server/ /vantage6/vantage6-server/

# copy startup scripts
COPY docker/server/ /vantage6/docker/server/
RUN ln -s /vantage6/docker/server/run.sh /run.sh

# install individual packages
RUN pip install -e /vantage6/vantage6-server

# expose server port
EXPOSE 80
