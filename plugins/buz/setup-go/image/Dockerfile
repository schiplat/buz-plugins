# syntax=docker/dockerfile:1
# buz/setup-go toolchain image: Go 1.26 native from the official image plus
# Go 1.25 and the gotip build (the `dev` alias) under /opt/go. Official
# release builds locate GOROOT relative to the toolchain directory, so moved
# trees work with an explicit GOROOT.
FROM golang:1.26-bookworm

LABEL org.opencontainers.image.source="https://github.com/schiplat/buz-plugins" \
      org.opencontainers.image.description="buz/setup-go toolchain image (go 1.26 native + 1.25/tip)"

COPY --from=golang:1.25-bookworm /usr/local/go /opt/go/1.25
COPY --from=golang:tip-bookworm /usr/local/go /opt/go/tip

RUN set -eux; \
    go version; \
    GOROOT=/opt/go/1.25 PATH=/opt/go/1.25/bin:$PATH go version; \
    GOROOT=/opt/go/tip PATH=/opt/go/tip/bin:$PATH go version

WORKDIR /buz/workspace
CMD ["sh"]
