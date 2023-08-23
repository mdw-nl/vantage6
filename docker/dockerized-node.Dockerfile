# Dockerfile for the node image
#
# IMAGES
# ------
# * harbor2.vantage6.ai/infrastructure/dockerized-node:x.x.x
#
ARG TAG=latest
# Why fixed 3.8
ARG BASE=3.8
FROM harbor2.vantage6.ai/infrastructure/dockerized-infrastructure-base:${BASE}

# will this TAG be read? It's set before FROM
LABEL version=${TAG}
LABEL maintainer="Frank Martin <f.martin@iknl.nl>"

# TODO: Are the below 3 lines needed for node?
# Fix DB issue
RUN apt install python-psycopg2 -y
RUN pip install psycopg2-binary

# copy sources
COPY vantage6-node /vantage6/vantage6-node
COPY vantage6-client /vantage6/vantage6-client

# copy startup scripts
COPY docker/node/ /vantage6/docker/node
RUN ln -s /vantage6/docker/node/run.sh /run.sh

# install individual packages
RUN pip install -e /vantage6/vantage6-node
# NodeClient extends BaseClient defined under vantage6-client. Althought it's already listed as a dependency in setup.py..
# TODO: how do we ensure we install this one instead?
# Is it a good idea to ship images with pip installl -e?
RUN pip install -e /vantage6/vantage6-client

# Node::__proxy_server_worker() will read this
ARG proxy_port=3128
ENV PROXY_SERVER_PORT ${proxy_port}
# expose proxy server port
# TODO: Is this actually necessary? Especially when Node::__proxy_server_worker() will try with random ports if this one didn't work?
#       And by default I think containers can talk to each other on any port while in the same network.
#       So, it they end up agreeing on a different port (why would they though?), this "EXPOSED" that shows up in docker ps would be misleading.
EXPOSE ${proxy_port}
