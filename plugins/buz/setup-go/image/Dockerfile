# syntax=docker/dockerfile:1
# buz/setup-go toolchain image: Go 1.26 native from the official image plus
# Go 1.25 under /opt/go/1.25. Official release builds locate GOROOT relative
# to the toolchain directory, so the moved tree works with an explicit GOROOT.
FROM golang:1.26-bookworm

COPY --from=golang:1.25-bookworm /usr/local/go /opt/go/1.25

RUN set -eux; \
    go version; \
    GOROOT=/opt/go/1.25 PATH=/opt/go/1.25/bin:$PATH go version

WORKDIR /buz/workspace
CMD ["sh"]
