# syntax=docker/dockerfile:1
# buz/setup-node toolchain image: Node.js 24 (active LTS) native from the
# official image plus Node.js 22 (maintenance LTS) under /opt/node/22. The
# node binary is relocatable and npm/corepack launch through env shebangs,
# so the copied tree works from anywhere on PATH.
FROM node:24-bookworm

COPY --from=node:22-bookworm /usr/local /opt/node/22

RUN set -eux; \
    node --version; \
    /opt/node/22/bin/node --version; \
    /opt/node/22/bin/npm --version

WORKDIR /buz/workspace
CMD ["sh"]
