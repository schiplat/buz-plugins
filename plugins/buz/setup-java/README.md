# Java build environment

Prepares a pinned Temurin JDK (21, 25, or 17) with `JAVA_HOME` exported for the step's `run:` commands. Maven and Gradle wrappers work out of the box.

```yaml
- name: build
  uses: buz/setup-java@1.1.0
  with:
    version: stable
    cache: true
  run: |
    ./mvnw -Dmaven.repo.local=/buz/workspace/.cache/java/m2 package
    # or: ./gradlew build
```

## How your commands run

The step's `run:` commands execute after the toolchain setup, in the same shell — everything the template exports (JAVA_HOME, GRADLE_USER_HOME, …) is visible to your commands. They start in the step directory: the template declares `default_dir: source`, and a step-level `work_dir` on the step overrides it. The directory must resolve physically inside the workspace.

`version` accepts `stable`/`lts` (= 21), `dev` (= 25, newest LTS), or `17`. With `cache: true` the Gradle home persists in `<workspace>/.cache/java/gradle`; for Maven pass `-Dmaven.repo.local=/buz/workspace/.cache/java/m2` to share the local repository. Each step is an isolated container — pass state between steps through workspace files. Requires a Docker-enabled Runner with egress to Maven Central / Gradle plugin portal.

## Versions in image 1.0.0

| `version` | Resolves to |
|-----------|-------------|
| `stable` (default), `lts` | Temurin JDK 21 (LTS) |
| `dev` | Temurin JDK 25 (LTS) |
| `17` | Temurin JDK 17 (LTS) |

Every run prints the resolved `java -version` as the first log line.

Version 1.0.0 templates remain unchanged and take the historical `script` and `workdir` inputs.
