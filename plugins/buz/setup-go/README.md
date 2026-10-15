# Go build environment

Runs POSIX `script` commands inside a pinned Go toolchain (1.26 or 1.25) with an explicit `GOROOT`. `dev` selects the gotip build frozen into the image.

```yaml
- name: build
  uses: buz/setup-go@1.0.0
  with:
    version: stable
    cache: true
    script: |
      go vet ./...
      go test ./...
```

`version` accepts `stable` (= 1.26), `lts` (= 1.25, previous release), `dev` (= gotip), or `1.25`/`1.26`. With `cache: true` the module and build caches persist in `<workspace>/.cache/go` across jobs on the same Runner. Each step is an isolated container — pass state between steps through workspace files. Requires a Docker-enabled Runner with egress to the Go module proxy.

## Versions in image 1.0.0

| `version` | Resolves to |
|-----------|-------------|
| `stable` (default), `1.26` | Go 1.26 |
| `lts`, `1.25` | Go 1.25 (previous release) |
| `dev` | gotip (development build frozen at image build time) |

Every run prints the resolved `go version` as the first log line.
