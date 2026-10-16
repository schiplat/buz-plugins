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
