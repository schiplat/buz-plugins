# Docker image build and push

Builds an OCI image from a build context inside the step directory and pushes it to a registry. Version 1.1.0 drives the Runner host daemon through the `docker-socket` capability and reuses the Runner's job-scoped Docker config (`/buz/workspace/.docker/config.json`) when present. A caller-supplied `DOCKER_CONFIG` always takes precedence.

```yaml
steps:
  - name: Build and push
    uses: buz/docker@1.1.0
    with:
      context: service-api
      tags: registry.example.com/app:1.2.0 registry.example.com/app:latest
      build_args: VERSION=1.2.0
```

The runner must grant the `docker-socket` capability. Credentials are read by
the Docker CLI for pulls and pushes. Build contexts are rejected if their
physical path includes the job workspace root, the Docker config directory,
or the job's `.buz` runtime directory; `.dockerignore` is not treated as a
security boundary. Keep `config.json` out of application contexts.
`context` and `dockerfile` resolve relative to the step directory — the
template declares `default_dir: source`, and a step-level `work_dir` on the
step overrides it. `dockerfile` (not `context`) is used as the `-f` argument
and must physically resolve inside the workspace; symlink escapes of either
path are rejected. A step-level `run:` appended by Buz executes after the
build/push, so follow-up commands (extra tagging, smoke checks) can react to
the built images.

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `tags` | string | yes | — | Space-separated full image references to tag and push |
| `context` | string | no | `.` | Existing path relative to the step directory; may not include the job root or the `.docker`/`.buz` directories |
| `dockerfile` | string | no | `Dockerfile` | Path relative to the step directory; physical symlink target must remain inside workspace |
| `build_args` | string | no | — | Space-separated `KEY=VALUE` build arguments |
| `push` | boolean | no | `true` | Push the tagged images after building |

Version 1.0.0 remains unchanged and requires explicit socket volume configuration.
Version 1.1.0 requires Buz 1.8.0 or newer.
