# Helm upgrade

Runs `helm upgrade --install --wait` on the Runner host against a Kubernetes
cluster, with the chart coming from the workspace. The cluster credential is
passed as a masked secret and written to a `0600` temp file for the duration
of the step only.

```yaml
steps:
  - name: Release
    uses: buz/helm-upgrade@1.0.0
    with:
      kubeconfig: ${secrets.KUBECONFIG}
      release: app
      chart: chart
      namespace: app-prod
      values: chart/values-production.yaml
      set: image.tag=1.2.0
```

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `kubeconfig` | string | yes | — | Full kubeconfig YAML for the target cluster (masked) |
| `release` | string | yes | — | Helm release name |
| `chart` | string | yes | — | Chart path, workspace-relative (local chart directory) |
| `namespace` | string | no | `default` | Target namespace (auto-created when missing) |
| `values` | string | no | — | Values file, workspace-relative |
| `set` | string | no | — | Space-separated `key=value` overrides |

## Notes

- **Requires `helm` (v3) on the Runner host** (shell engine runs there) —
  Helm talks to the cluster API directly, no `kubectl` needed. Use a
  least-privileged ServiceAccount kubeconfig.
- `--wait --timeout 10m` is always applied so the step fails when the
  release does not become ready.
- Pair with `buz/net-check` when the workload exposes an endpoint.
