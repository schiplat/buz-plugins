# Docker Compose deployment

Deploys a Docker Compose project on the target SSH host: pulls images, recreates
containers (`up -d --force-recreate --remove-orphans`), and prints `compose ps`.
Runs on the host — Docker and the compose file must already exist there.

```yaml
steps:
  - name: Deploy
    uses: buz/docker-compose@1.0.0
    host: $deploy_host
    registry_secret: ${secrets.REGISTRY}
    with:
      project_dir: /opt/app
      image: registry.example.com/app:1.2.0
      services: api worker
```

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `project_dir` | string | yes | — | Absolute path on the target host containing the compose file |
| `compose_file` | string | no | `docker-compose.yml` | Compose file name inside `project_dir` |
| `image` | string | no | — | Image reference exported as `IMAGE` — reference `${IMAGE:-}` in the compose file |
| `services` | string | no | all | Space-separated service names to recreate |
| `pull` | boolean | no | `true` | Run `docker compose pull` before up |

## Notes

- The step-level `host:` selects the target host and `registry_secret:` performs
  the registry login natively (both are Buz step fields, not inputs). The step
  fails at dispatch if `host:` is missing.
- Reference the injected image via the `${IMAGE:-}` environment variable inside
  the compose file; pass the tag from a trigger input.
- Requires Buz 1.7.5+ (`requires_buz`). Image pulls run on the target host's
  Docker daemon — outside the template egress checker's view.
- Pair with [`buz/http-check`](../http-check/README.md) after this step for
  readiness polling, and store registry/webhook values as Manager Secrets.
