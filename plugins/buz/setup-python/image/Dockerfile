# syntax=docker/dockerfile:1
# buz/setup-python toolchain image: Python 3.14 native (official image build)
# plus 3.13 and 3.12 copied from their official images. CPython locates its
# stdlib relative to the executable and the copied trees keep the official
# layout; ldconfig covers libpython for the moved versions and the build-time
# smoke tests import compiled extensions to prove each interpreter works.
FROM python:3.14-bookworm

COPY --from=python:3.13-bookworm /usr/local /opt/python/3.13
COPY --from=python:3.12-bookworm /usr/local /opt/python/3.12

RUN set -eux; \
    printf '/opt/python/3.13/lib\n' > /etc/ld.so.conf.d/buz-python-3.13.conf; \
    printf '/opt/python/3.12/lib\n' > /etc/ld.so.conf.d/buz-python-3.12.conf; \
    ldconfig; \
    sed -i 's|^#!/usr/local/bin/python3.13|#!/opt/python/3.13/bin/python3.13|' \
      /opt/python/3.13/bin/pip3.13 /opt/python/3.13/bin/pip3; \
    sed -i 's|^#!/usr/local/bin/python3.12|#!/opt/python/3.12/bin/python3.12|' \
      /opt/python/3.12/bin/pip3.12 /opt/python/3.12/bin/pip3; \
    python3.14 --version; \
    /opt/python/3.13/bin/python3.13 -c 'import ensurepip, ssl; print("3.13 ok")'; \
    /opt/python/3.12/bin/python3.12 -c 'import ensurepip, ssl; print("3.12 ok")'

WORKDIR /buz/workspace
CMD ["sh"]
