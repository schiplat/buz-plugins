# Docker logout (Runner host)

Best-effort `docker logout` — the cleanup counterpart of `buz/docker-login`.

```yaml
- name: registry logout
  uses: buz/docker-logout@1.0.0
  with:
    registry: registry.example.com
```

Local job-scoped credentials are removed by the Runner when the job ends regardless, so this step is about hygiene for shared runners and the legacy `shared` isolation mode. Not logged in is not an error — the step reports and succeeds. For logins on deploy target hosts, pair with the same template under `engine: ssh`:

```yaml
- name: registry logout on target
  uses: buz/docker-logout@1.0.0
  engine: ssh
  host:
    - web-01
  with:
    registry: registry.example.com
```

On target hosts the template also removes the job-scoped `/tmp/buz-docker-*` credential dir (guarded: never an unset or host-global `DOCKER_CONFIG`).
