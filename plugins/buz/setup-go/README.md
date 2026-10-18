# Go build environment

Prepares a pinned Go toolchain (1.26 or 1.25) with an explicit `GOROOT` for the step's `run:` commands. `dev` selects the gotip build frozen into the image.

```yaml
- name: build
  uses: buz/setup-go@1.1.0
  with:
    version: stable
    cache: true
  run: |
    go vet ./...
    go test ./...
```

## How your commands run

The step's `run:` commands execute after the toolchain setup, in the same shell — everything the template exports (GOROOT, GOPATH, GOCACHE, …) is visible to your commands. They start in the step directory: the template declares `default_dir: source`, and a step-level `work_dir` on the step overrides it. The directory must resolve physically inside the workspace.

`version` accepts `stable` (= 1.26), `lts` (= 1.25, previous release), `dev` (= gotip), or `1.25`/`1.26`. With `cache: true` the module and build caches persist in `<workspace>/.cache/go` across jobs on the same Runner. Each step is an isolated container — pass state between steps through workspace files. Requires a Docker-enabled Runner with egress to the Go module proxy.

## Versions in image 1.0.0

| `version` | Resolves to |
|-----------|-------------|
| `stable` (default), `1.26` | Go 1.26 |
| `lts`, `1.25` | Go 1.25 (previous release) |
| `dev` | gotip (development build frozen at image build time) |

Every run prints the resolved `go version` as the first log line.

Version 1.0.0 templates remain unchanged and take the historical `script` and `workdir` inputs.
