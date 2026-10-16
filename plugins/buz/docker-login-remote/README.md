# Docker login (deploy target hosts)

Logs the Docker CLI into a registry on the deploy target hosts, so later ssh steps on the same hosts can pull private images — e.g. `docker compose pull`. Runs via `engine: ssh`: set the step-level `host:` list (Manager-resolved). Requires the Docker CLI on the target hosts.

```yaml
- name: registry login on target
  uses: buz/docker-login-remote@1.0.0
  host:
    - web-01
  with:
    registry: registry.example.com
    username: deploy
    password: ${secrets.REGISTRY_PASSWORD}
```

Credentials land in a job-scoped config dir under `/tmp` on each target host and are shared by later ssh steps of the same job on that host. **Always pair with `buz/docker-logout-remote` as the last step**, and mark failure-prone earlier steps `continue-on-error` so the logout still runs. A cancelled job cannot run the logout — remote residue then waits for the host's `/tmp` cleanup.
