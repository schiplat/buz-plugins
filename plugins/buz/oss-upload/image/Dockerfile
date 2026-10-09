# syntax=docker/dockerfile:1
FROM debian:bookworm-slim

ARG OSSUTIL_VERSION=2.4.0
ARG OSSUTIL_SHA256_AMD64=85edf66b2fb7238f5c7e25cab820cf29312319fe4935b7c86a6b8485eb434f3c

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl unzip \
    && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    archive="ossutil-${OSSUTIL_VERSION}-linux-amd64.zip"; \
    curl --fail --location --silent --show-error "https://gosspublic.alicdn.com/ossutil/v2/${OSSUTIL_VERSION}/${archive}" -o "/tmp/${archive}"; \
    echo "${OSSUTIL_SHA256_AMD64}  /tmp/${archive}" | sha256sum --check -; \
    unzip -q "/tmp/${archive}" -d /tmp/ossutil; \
    install -m 0755 "/tmp/ossutil/ossutil-${OSSUTIL_VERSION}-linux-amd64/ossutil" /usr/local/bin/ossutil; \
    rm -rf /tmp/ossutil "/tmp/${archive}"; \
    ossutil version

COPY entrypoint.sh /usr/local/bin/buz-oss-upload
RUN chmod 0755 /usr/local/bin/buz-oss-upload

WORKDIR /buz/workspace
CMD ["sh"]
