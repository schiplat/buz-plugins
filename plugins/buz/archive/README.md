# Archive workspace paths

Packs workspace-relative files or directories into a `tar.gz` archive and
writes a `sha256` checksum next to it. Pair with
[`buz/oss-upload`](../oss-upload/README.md) or
[`buz/s3-upload`](../s3-upload/README.md) to publish the archive.

```yaml
steps:
  - name: Package
    uses: buz/archive@1.0.0
    with:
      paths: dist configs/docker-compose.yml
      output: release/app-1.2.0.tar.gz
```

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `paths` | string | yes | — | Space-separated workspace-relative files/directories to pack |
| `output` | string | yes | — | Archive path to create, workspace-relative (parent dirs auto-created) |

## Notes

- Produces `<output>` plus `<output>.sha256` (standard `sha256sum` format —
  verify with `sha256sum -c`).
- Paths are validated as workspace-relative; absolute paths and `..` escapes
  are rejected.
- Engine: shell (runs on the Runner host, workspace as working directory).
  Each step is an isolated container-free process — pass archives to later
  steps through workspace files.
