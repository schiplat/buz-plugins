# Java build environment

Runs POSIX `script` commands inside a pinned Temurin JDK (21, 25, or 17) with `JAVA_HOME` exported. Maven and Gradle wrappers work out of the box.

```yaml
- name: build
  uses: buz/setup-java@1.0.0
  with:
    version: stable
    cache: true
    script: |
      ./mvnw -Dmaven.repo.local=/buz/workspace/.cache/java/m2 package
      # or: ./gradlew build
```

`version` accepts `stable`/`lts` (= 21), `dev` (= 25, newest LTS), or `17`. With `cache: true` the Gradle home persists in `<workspace>/.cache/java/gradle`; for Maven pass `-Dmaven.repo.local=/buz/workspace/.cache/java/m2` to share the local repository. Each step is an isolated container — pass state between steps through workspace files. Requires a Docker-enabled Runner with egress to Maven Central / Gradle plugin portal.

## Versions in image 1.0.0

| `version` | Resolves to |
|-----------|-------------|
| `stable` (default), `lts` | Temurin JDK 21 (LTS) |
| `dev` | Temurin JDK 25 (LTS) |
| `17` | Temurin JDK 17 (LTS) |

Every run prints the resolved `java -version` as the first log line.
