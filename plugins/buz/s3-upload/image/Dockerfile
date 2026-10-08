# syntax=docker/dockerfile:1
FROM debian:bookworm-slim

ARG TARGETARCH
ARG AWSCLI_VERSION=2.27.41

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg unzip \
    && rm -rf /var/lib/apt/lists/*

COPY aws-cli-team-public-key.asc /tmp/aws-cli-team.asc
RUN set -eux; \
    case "$TARGETARCH" in \
      amd64) arch=x86_64 ;; \
      arm64) arch=aarch64 ;; \
      *) echo "unsupported architecture: $TARGETARCH" >&2; exit 1 ;; \
    esac; \
    archive="awscli-exe-linux-${arch}-${AWSCLI_VERSION}.zip"; \
    curl --fail --location --silent --show-error "https://awscli.amazonaws.com/${archive}" -o "/tmp/${archive}"; \
    curl --fail --location --silent --show-error "https://awscli.amazonaws.com/${archive}.sig" -o "/tmp/${archive}.sig"; \
    fingerprint="$(gpg --show-keys --with-colons /tmp/aws-cli-team.asc | awk -F: '$1 == "fpr" { print $10; exit }')"; \
    test "$fingerprint" = "FB5DB77FD5C18B805111ADA8A6310ACC4672475C"; \
    gpg --batch --import /tmp/aws-cli-team.asc; \
    gpg --batch --verify "/tmp/${archive}.sig" "/tmp/${archive}"; \
    unzip -q "/tmp/${archive}" -d /tmp/aws-cli; \
    /tmp/aws-cli/aws/install --install-dir /usr/local/aws-cli --bin-dir /usr/local/bin; \
    rm -rf /tmp/aws-cli /tmp/aws-cli-team.asc "/tmp/${archive}" "/tmp/${archive}.sig" /root/.gnupg; \
    aws --version

COPY entrypoint.sh /usr/local/bin/buz-s3-upload
RUN chmod 0755 /usr/local/bin/buz-s3-upload

WORKDIR /buz/workspace
CMD ["sh"]
