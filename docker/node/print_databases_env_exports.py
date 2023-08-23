#!/usr/bin/env python3
#
# Print environment variable exports ready to be eval'd, so vantage6 gets the
# right config for databases.
#
# This is because if vantage6 detects it's running inside docker, it will sort
# of ignore the 'uri' setting for 'databases' in the config file [0]. Instead
# it will read 'uri' from env var '{label_upper}_DATABASE_URI'. So we print the
# `export` of those variables ready to be `eval`ed. Vantage6 will prepend '/mnt'
# to the path. And we well mount the databases volume to `/mnt/databases`.
#
# (Readying yaml in bash is less than ideal, hence this python script)
#
# [0]: https://github.com/vantage6/vantage6/blob/version/3.10.3/vantage6-node/vantage6/node/docker/docker_manager.py#L197-L216

import yaml

# FIXME: hard-coded path! But this whole hack to deal with v6's databases needs
# fixing. It might make sense to modify vantage6 itself.
PATH_DATABASES_CONFIG = '/mnt/config/config.yaml'

with open(PATH_DATABASES_CONFIG, 'r') as f:
    databases = yaml.safe_load(f)['application']['databases']

for database in databases:
    print(f"export {database['label'].upper()}_DATABASE_URI=\"/databases/{database['uri']}\"")
