# syntax=docker/dockerfile:1
# buz/setup-java toolchain image: Temurin JDK 21 native plus JDK 25 and 17
# copied from their official images (temurin relocates fine — the java
# launcher resolves its home from the binary location).
FROM eclipse-temurin:21-jdk-bookworm

LABEL org.opencontainers.image.source="https://github.com/schiplat/buz-plugins" \
      org.opencontainers.image.description="buz/setup-java toolchain image (temurin 21 native + 25/17)"

COPY --from=eclipse-temurin:25-jdk-bookworm /opt/java/openjdk /opt/java/25
COPY --from=eclipse-temurin:17-jdk-bookworm /opt/java/openjdk /opt/java/17

RUN set -eux; \
    java -version; \
    /opt/java/25/bin/java -version; \
    /opt/java/17/bin/java -version

WORKDIR /buz/workspace
CMD ["sh"]
