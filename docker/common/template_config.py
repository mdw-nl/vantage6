#!/usr/bin/env python3
#
# Templates config file allowing use of environment variables starting with ENV_
# and provides a read_secret filter.
#
# In:
#   - env vars (starting with 'ENV_')
#   - template file
# Out:
#   - rendered template file
#
# NOTE: This is intended as a temporary solution. The simple alternative to this
# would be to simply let the user volume-map a final config file.  But at the
# moment, there's a few unavoidable secrets that need to be written into that
# config file, and we'd rather make the passing of those secrets more explicit.
# Also, this lets the user not provide a config file and use a default one, while
# providing the minimum flexibility necessary to have a working server/node for
# development (via default config template and V6_* vars)

import os
import argparse
from jinja2 import Environment, StrictUndefined, FileSystemLoader
from pathlib import Path


def read_secret(secret_path):
    """
    Simple filter for jinja2 to read a file from a path

    :param secret_path: path to file to read

    Examples:
    ```
    {{ "/path/to/secret" | read_secret }}

    {{ ENV_SOME_PASSWORD_FILE | read_secret }}
    ```
    """
    with open(secret_path, "r") as secret_file:
        return secret_file.read().strip()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("template", help="Path to template (.j2)", type=Path)
    parser.add_argument("output", help="Path to output file (config)", type=Path)
    parser.add_argument("--extra-dirs", help="Extra directories to search for templates (useful for 'includes')", nargs="*")
    args = parser.parse_args()
    if not args.template.exists():
        raise Exception(f"Template file at {args.template} does not seem to exist!")
    if args.output.exists():
        raise Exception(f"Output file at {args.output} already exists! Won't override")
    return args


def main():
    args = parse_args()

    # add extra directories to search for templates
    templates_dirs = [args.template.parent]

    if args.extra_dirs:
        templates_dirs.extend(args.extra_dirs)

    # load jinja2 environment
    j2_env = Environment(
        loader=FileSystemLoader(templates_dirs),
        undefined=StrictUndefined
    )

    # load read_secret filter
    j2_env.filters['read_secret'] = read_secret

    template = j2_env.get_template(args.template.name)

    # render template passing all V6_* environment variables
    try:
      templated = template.render({k:v for (k, v) in os.environ.items() if k.startswith('V6_')})
    except TypeError as e:
        # TODO: this is hacky, is there a better way to get TypeError's culprit's name?
        if 'StrictUndefined' in str(e):
            raise Exception(f"Template {args.template} contains undefined variables! Please check your template and env variables provided.")

    # write out rendered template
    old_umask = os.umask(0o077)
    with open(args.output, "w") as output_file:
        output_file.write(templated)
    os.umask(old_umask)


if __name__ == "__main__":
    main()
