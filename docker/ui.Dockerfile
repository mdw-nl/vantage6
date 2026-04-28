# We pin the release bases so rebuilding a tag does not silently move to a
# different Node or nginx image. These digests are the linux/amd64 manifests,
# matching the current release workflow platform.
# node:20-alpine3.23
# https://hub.docker.com/layers/library/node/20-alpine3.23/images/sha256-afdf98210b07b586eb71fa22ba2e432e058e4cd1304d31ed60888755b8c865fb
FROM node:20-alpine3.23@sha256:afdf98210b07b586eb71fa22ba2e432e058e4cd1304d31ed60888755b8c865fb AS node

# copy and install
WORKDIR /app
COPY vantage6-ui/ /app
RUN npm ci
RUN npm run build

# run
# nginx:1.30-alpine3.23
# https://hub.docker.com/layers/library/nginx/1.30-alpine3.23/images/sha256-e544ba68e68ddbcdff106010fa82f4ab30378899e78d4ff7aadf4ef5a7c65091
FROM nginx:1.30-alpine3.23@sha256:e544ba68e68ddbcdff106010fa82f4ab30378899e78d4ff7aadf4ef5a7c65091

LABEL maintainer="Bart van Beusekom <b.vanbeusekom@iknl.nl>, Frank Martin <f.martin@iknl.nl>"

COPY --from=node /app/startup /app/startup
COPY --from=node /app/dist/vantage6-UI/browser /usr/share/nginx/html

# Copy nginx config file to container
COPY vantage6-ui/nginx.conf /etc/nginx/nginx.conf

RUN chmod +x /app/startup/replace_env_vars.sh

# When the container starts, replace the env.js with values from environment variables and then startup app
CMD ["/bin/sh",  "-c",  "/app/startup/replace_env_vars.sh && exec nginx -g 'daemon off;'"]
