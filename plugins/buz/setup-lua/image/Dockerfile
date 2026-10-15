# syntax=docker/dockerfile:1
# buz/setup-lua toolchain image: Debian-packaged lua5.4, lua5.3 and luajit
# (2.1). `version` selects the interpreter through PATH symlinks under
# /opt/lua, so upstream Debian signing covers every interpreter binary.
FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates lua5.4 lua5.3 luajit \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /opt/lua/5.4/bin /opt/lua/5.3/bin /opt/lua/jit/bin \
    && ln -s /usr/bin/lua5.4 /opt/lua/5.4/bin/lua \
    && ln -s /usr/bin/luac5.4 /opt/lua/5.4/bin/luac \
    && ln -s /usr/bin/lua5.3 /opt/lua/5.3/bin/lua \
    && ln -s /usr/bin/luac5.3 /opt/lua/5.3/bin/luac \
    && ln -s /usr/bin/luajit /opt/lua/jit/bin/luajit \
    && lua5.4 -v \
    && lua5.3 -v \
    && luajit -v

WORKDIR /buz/workspace
CMD ["sh"]
