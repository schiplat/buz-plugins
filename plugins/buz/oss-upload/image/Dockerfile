# syntax=docker/dockerfile:1
FROM debian:bookworm-slim

ARG TARGETARCH
ARG OSSUTIL_VERSION=2.4.0
ARG OSSUTIL_SHA256_AMD64=85edf66b2fb7238f5c7e25cab820cf29312319fe4935b7c86a6b8485eb434f3c
ARG OSSUTIL_SHA256_ARM64=7767240e9667d1f26fbe4e04f90b796b4356889e77d0076cc8a543c8ce081987

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl unzip \
    && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    case "$TARGETARCH" in \
      amd64) arch=amd64; expected="$OSSUTIL_SHA256_AMD64" ;; \
      arm64) arch=arm64; expected="$OSSUTIL_SHA256_ARM64" ;; \
      *) echo "unsupported architecture: $TARGETARCH" >&2; exit 1 ;; \
    esac; \
    archive="ossutil-${OSSUTIL_VERSION}-linux-${arch}.zip"; \
    curl --fail --location --silent --show-error "https://gosspublic.alicdn.com/ossutil/v2/${OSSUTIL_VERSION}/${archive}" -o "/tmp/${archive}"; \
    echo "${expected}  /tmp/${archive}" | sha256sum --check -; \
    unzip -q "/tmp/${archive}" -d /tmp/ossutil; \
    install -m 0755 /tmp/ossutil/ossutil /usr/local/bin/ossutil; \
    rm -rf /tmp/ossutil "/tmp/${archive}"; \
    ossutil version

COPY entrypoint.sh /usr/local/bin/buz-oss-upload
RUN chmod 0755 /usr/local/bin/buz-oss-upload

WORKDIR /buz/workspace
CMD ["sh"]
