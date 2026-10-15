# Docker image build and push

Builds an OCI image from a workspace build context and pushes it to a
registry. The step drives the Runner host's Docker daemon through the mounted
socket (docker-out-of-docker) — the built image lands on the host Docker as
well.

```yaml
steps:
  - name: Build and push
    uses: buz/docker@1.0.0
    registry_secret: ${secrets.REGISTRY}
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    with:
      context: service-api
      tags: registry.example.com/app:1.2.0 registry.example.com/app:latest
      build_args: VERSION=1.2.0
```

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `tags` | string | yes | — | Space-separated full image references to tag and push |
| `context` | string | no | `.` | Build context, workspace-relative |
| `dockerfile` | string | no | `Dockerfile` | Dockerfile path, workspace-relative |
| `build_args` | string | no | — | Space-separated `KEY=VALUE` build arguments |
| `push` | boolean | no | `true` | Push the tagged images after building |

## Notes

- **Required step configuration** (both are Buz step fields, not inputs):
  - `volumes: [/var/run/docker.sock:/var/run/docker.sock]` — without the
    socket the step fails with "docker daemon unreachable";
  - `registry_secret: ${secrets.*}` — performs the registry login on the host
    daemon; pushes from the step reuse that auth.
- The host daemon performs the build — the Runner host needs egress to the
  registry and to any base-image registries referenced by the Dockerfile.
- Each step is an isolated container — pass state between steps through
  workspace files.
