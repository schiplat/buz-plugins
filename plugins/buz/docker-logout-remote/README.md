# Docker logout (deploy target hosts)

Best-effort `docker logout` on the deploy target hosts (set the step-level `host:` list, same hosts as the login step) — plus removal of the job-scoped credential dir under `/tmp`. The cleanup counterpart of `buz/docker-login-remote`.

```yaml
- name: registry logout on target
  uses: buz/docker-logout-remote@1.0.0
  host:
    - web-01
  with:
    registry: registry.example.com
```

Not logged in is not an error — the step reports and succeeds. The `/tmp/buz-docker-*` dir is only removed when `DOCKER_CONFIG` matches that prefix, never an unset or host-global value.
