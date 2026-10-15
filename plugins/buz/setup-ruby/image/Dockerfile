# syntax=docker/dockerfile:1
# buz/setup-ruby toolchain image: ruby 3.4 native (official image build) plus
# a source-built ruby 3.3 under /opt/ruby/3.3. 3.3 is EOL upstream and kept
# only for existing applications; `version` selects the interpreter via PATH.
FROM ruby:3.4-bookworm

LABEL org.opencontainers.image.source="https://github.com/schiplat/buz-plugins" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.description="buz/setup-ruby toolchain image (ruby 3.4 native + 3.3)"

ARG RUBY33_VERSION=3.3.6

RUN set -eux; \
    curl --fail --location --silent --show-error \
      "https://cache.ruby-lang.org/pub/ruby/${RUBY33_VERSION%.*}/ruby-${RUBY33_VERSION}.tar.xz" \
      -o /tmp/ruby33.tar.xz; \
    mkdir -p /usr/src/ruby33; \
    tar -xJf /tmp/ruby33.tar.xz -C /usr/src/ruby33 --strip-components=1; \
    cd /usr/src/ruby33; \
    ./configure --prefix=/opt/ruby/3.3 --disable-install-doc; \
    make -j"$(nproc)"; \
    make install; \
    cd /; \
    rm -rf /usr/src/ruby33 /tmp/ruby33.tar.xz; \
    printf '/opt/ruby/3.3/lib\n' > /etc/ld.so.conf.d/buz-ruby-3.3.conf; \
    ldconfig; \
    /opt/ruby/3.3/bin/ruby --version; \
    ruby --version

WORKDIR /buz/workspace
CMD ["sh"]
