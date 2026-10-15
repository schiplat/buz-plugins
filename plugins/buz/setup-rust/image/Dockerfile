# syntax=docker/dockerfile:1
# buz/setup-rust toolchain image: rustup plus the stable toolchain frozen at
# build time. A `version` input other than "stable" installs that toolchain on
# demand at run time (rustup download on the Runner; pair with cache: true to
# persist the cargo registry across jobs via the workspace cache).
FROM rust:1-bookworm

LABEL org.opencontainers.image.source="https://github.com/schiplat/buz-plugins" \
      org.opencontainers.image.description="buz/setup-rust toolchain image (rustup + stable)"

WORKDIR /buz/workspace
CMD ["sh"]
