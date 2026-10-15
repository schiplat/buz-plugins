# syntax=docker/dockerfile:1
# buz/docker tool image: Docker CLI only. The step drives the host daemon
# through the socket mounted by the pipeline step (docker-out-of-docker), so
# builds and pushes run against the Runner's Docker.
FROM docker:cli

WORKDIR /buz/workspace
CMD ["sh"]
