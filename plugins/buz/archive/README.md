# Archive — pack & extract

Two modes in one template (`engines: [shell, ssh]`):

- **`mode: pack` (default, `engine: shell`)** — packs workspace-relative files or directories into a `tar.gz` archive and writes a `sha256` checksum next to it. Pair with [`buz/oss-upload`](../oss-upload/README.md) / [`buz/s3-upload`](../s3-upload/README.md) to publish, or [`buz/scp`](../scp/README.md) to deliver to a target host.
- **`mode: extract` (`engine: ssh`)** — unpacks a tar.gz that is already on the deploy target hosts into an absolute directory. Pair with [`buz/scp`](../scp/README.md) (delivery leg) and a `config.render` block (render-only) for the config flow.

## Pack (Runner workspace)

```yaml
steps:
  - name: Package
    uses: buz/archive@1.0.0
    with:
      paths: src dist README.md
      output: dist/release.tar.gz
```

`paths` is space-separated, workspace-relative; `output` is workspace-relative (a `.sha256` checksum is written alongside). Both required.

## Extract (target hosts, 1.1.0+)

```yaml
steps:
  - name: Unpack config bundle
    uses: buz/archive@1.1.0
    engine: ssh
    host:
      - web-01
    with:
      mode: extract
      archive: /opt/cella/configs.tar.gz   # absolute, on the target host
      dest: /opt/cella                     # absolute; created as needed
```

`archive` and `dest` are **absolute paths on the target host**. Requires `tar` on the target hosts. Typical chain: [`buz/oss-download`](../oss-download/README.md) downloads the bundle to the Runner workspace → [`buz/scp`](../scp/README.md) delivers it → this step unpacks it → `config.render` (render-only) renders the env files.
