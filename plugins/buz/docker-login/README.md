# Docker login (Runner host)

Logs the Docker CLI into a container registry so later steps can pull or push private images — `docker build`/`docker push` in shell steps, and `engine: docker` pulls. Requires the Docker CLI on the runner host.

```yaml
- name: registry login
  uses: buz/docker-login@1.0.0
  with:
    registry: registry.example.com
    username: deploy
    password: ${secrets.REGISTRY_PASSWORD}
```

All three inputs are required. The password is delivered via `--password-stdin` (never a CLI argument) and masked in logs.

Credentials land in the job-scoped Docker config dir (`DOCKER_CONFIG`, see the Runner `docker_config_isolation` setting) and are removed when the job ends — success, failure, or cancel. On shared runners, or with the legacy `shared` isolation mode, pair with `buz/docker-logout`. Multiple registries: one step each.

**Target hosts (`engine: ssh`)** — the template declares `engines: [shell, ssh]`, so the same step can log in on the pipeline's target hosts instead of the Runner. Later ssh steps on the same hosts (compose pull, etc.) reuse that login; the job-scoped dir lives under `/tmp` on each host.

```yaml
- name: registry login on target
  uses: buz/docker-login@1.0.0
  engine: ssh          # call-site override; also declared in the template (engines)
  host:
    - web-01
  with:
    registry: registry.example.com
    username: deploy
    password: ${secrets.REGISTRY_PASSWORD}
```

Pair with `buz/docker-logout` (`engine: ssh`, same `host:` list) as the last step.
