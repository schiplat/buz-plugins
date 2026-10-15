# syntax=docker/dockerfile:1
# buz/setup-php toolchain image: PHP 8.4 native (official image build) plus
# PHP 8.3 under /opt/php/8.3. The copied 8.3 tree keeps its compiled-in
# /usr/local paths, so selecting 8.3 also selects PHPRC=/opt/php/8.3/etc,
# where a generated php.ini overrides extension_dir. Composer is shared.
FROM php:8.4-bookworm

LABEL org.opencontainers.image.source="https://github.com/schiplat/buz-plugins" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.description="buz/setup-php toolchain image (php 8.4 native + 8.3, composer)"

ARG COMPOSER_VERSION=2.10.3

COPY --from=php:8.3-bookworm /usr/local /opt/php/8.3

RUN set -eux; \
    api_dir="$(ls /opt/php/8.3/lib/php/extensions)"; \
    mkdir -p /opt/php/8.3/etc; \
    printf 'extension_dir=/opt/php/8.3/lib/php/extensions/%s\n' "$api_dir" \
      > /opt/php/8.3/etc/php.ini; \
    sed -i 's|/usr/local|/opt/php/8.3|g' /opt/php/8.3/bin/php-config /opt/php/8.3/bin/phpize; \
    curl --fail --location --silent --show-error \
      "https://getcomposer.org/download/${COMPOSER_VERSION}/composer.phar" \
      -o /usr/local/bin/composer; \
    curl --fail --location --silent --show-error \
      "https://getcomposer.org/download/${COMPOSER_VERSION}/composer.phar.sha256sum" \
      -o /tmp/composer.phar.sha256sum; \
    echo "$(cut -d' ' -f1 /tmp/composer.phar.sha256sum)  /usr/local/bin/composer" \
      | sha256sum --check -; \
    chmod 0755 /usr/local/bin/composer; \
    rm -f /tmp/composer.phar.sha256sum; \
    php --version; \
    PHPRC=/opt/php/8.3/etc/php.ini /opt/php/8.3/bin/php --version

WORKDIR /buz/workspace
CMD ["sh"]
