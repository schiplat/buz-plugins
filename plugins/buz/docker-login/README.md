# Docker login (Runner host)

Logs the Docker CLI into a container registry so later steps can pull or push private images — `docker build`/`docker push` in shell steps, and `engine: docker` pulls. Requires the Docker CLI on the runner host.

```yaml
- name: registry login
  uses: buz/docker-login@1.1.0
  with:
    registry: registry.example.com
    username: deploy
    password: ${secrets.REGISTRY_PASSWORD}
```

The three authentication inputs (`registry`, `username`, `password`) are required. The password must be a complete `${secrets.NAME}` reference and is delivered via `--password-stdin` (never a CLI argument) and masked in logs.

Version `1.1.0` adds optional `debug` (boolean, default `false`). To enable it:

```yaml
- name: registry login with diagnostics
  uses: buz/docker-login@1.1.0
  with:
    registry: registry.example.com
    username: ${secrets.REGISTRY_USERNAME}
    password: ${secrets.REGISTRY_PASSWORD}
    debug: "true"
```

Debug output shows the login command with username/password redacted, the Docker config directory, and the Docker login exit code. It does not print credential values or enable shell tracing (`set -x`). A failed login retains Docker's non-zero exit code; debug does not make failures non-blocking. This template input is independent of the Manager's job-level debug mode and does not disable log masking. Existing `@1.0.0` pipelines remain unchanged.

Credentials land in the job-scoped Docker config dir (`DOCKER_CONFIG`, see the Runner `docker_config_isolation` setting) and are removed when the job ends — success, failure, or cancel. On shared runners, or with the legacy `shared` isolation mode, pair with `buz/docker-logout`. Multiple registries: one step each.

**Target hosts (`engine: ssh`)** — the template declares `engines: [shell, ssh]`, so the same step can log in on the pipeline's target hosts instead of the Runner. Later ssh steps on the same hosts (compose pull, etc.) reuse that login; the job-scoped dir lives under `/tmp` on each host.

```yaml
- name: registry login on target
  uses: buz/docker-login@1.1.0
  engine: ssh          # call-site override; also declared in the template (engines)
  host:
    - web-01
  with:
    registry: registry.example.com
    username: deploy
    password: ${secrets.REGISTRY_PASSWORD}
```

Pair with `buz/docker-logout` (`engine: ssh`, same `host:` list) as the last step.
