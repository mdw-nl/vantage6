FROM python:3.10-slim-buster

LABEL version="3"
LABEL maintainer="Frank Martin <f.martin@iknl.nl>"

# slim buster does not have gcc installed
# libdev is needed for arm compilation
RUN apt-get update \
    && apt-get install -y gcc python3-dev libffi-dev

# TODO: Do we need this for node?
# Overwrite uWSGI installation from the requirements.txt
# Install uWSGI from source (for RabbitMQ)
RUN apt-get install --no-install-recommends --no-install-suggests -y \
  libssl-dev python3-setuptools
RUN CFLAGS="-I/usr/local/opt/openssl/include" \
  LDFLAGS="-L/usr/local/opt/openssl/lib" \
  UWSGI_PROFILE_OVERRIDE=ssl=true \
  pip install uwsgi -Iv

# TODO: Are the below 3 lines needed for node?
# Fix DB issue
RUN apt install python-psycopg2 -y
RUN pip install psycopg2-binary

# copy common sources
# docker unfortunately does not support copying directories, only its contents.
#ADD vantage6/ vantage6-common/ /vantage6/
COPY vantage6/ /vantage6/vantage6/
COPY vantage6-common/ /vantage6/vantage6-common/
COPY requirements.txt README.md /vantage6/
#COPY . /vantage6/

# TODO: maybe requirements could be split for node and server?
# install requirements. We cannot rely on setup.py because of the way
# python resolves package versions. To control all dependencies we install
# them from the requirements.txt
RUN pip install -r /vantage6/requirements.txt
    # piwheels is for ARM
    #--extra-index-url https://www.piwheels.org/simple

# install individual common packages
RUN pip install -e /vantage6/vantage6-common
RUN pip install -e /vantage6/vantage6

COPY docker/common/ /vantage6/docker/common/

#RUN pip install -e /vantage6/vantage6-client  # common?

