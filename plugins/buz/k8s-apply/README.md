# Kubernetes apply

Applies a manifest from the workspace to a Kubernetes cluster with `kubectl
apply -f`, optionally server-side, then prints the latest namespace events.
The cluster credential is passed as a masked secret and written to a `0600`
temp file for the duration of the step only.

```yaml
steps:
  - name: Apply
    uses: buz/k8s-apply@1.0.0
    with:
      kubeconfig: ${secrets.KUBECONFIG}
      manifest: k8s/app.yaml
      namespace: app-prod
```

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `kubeconfig` | string | yes | — | Full kubeconfig YAML for the target cluster (masked) |
| `manifest` | string | yes | — | Manifest file, workspace-relative |
| `namespace` | string | no | manifest default | Target namespace |
| `server_side` | boolean | no | `false` | Use `--server-side` apply |

## Notes

- **Requires `kubectl` on the Runner host** (shell engine runs there). Use a
  least-privileged ServiceAccount kubeconfig — namespace-scoped, no cluster
  admin.
- The kubeconfig temp file is removed when the step process exits; secrets
  are additionally masked in streamed logs.
- Pair with a `kubectl rollout status` follow-up (via the same pattern) or a
  `buz/http-check` step when the workload exposes an endpoint.
