# Docker logout (Runner host)

Best-effort `docker logout` — the cleanup counterpart of `buz/docker-login`.

```yaml
- name: registry logout
  uses: buz/docker-logout@1.0.0
  with:
    registry: registry.example.com
```

Local job-scoped credentials are removed by the Runner when the job ends regardless, so this step is about hygiene for shared runners and the legacy `shared` isolation mode. Not logged in is not an error — the step reports and succeeds. For logins on deploy target hosts, pair with `buz/docker-logout-remote` instead.
