# Node.js build environment

Prepares a pinned Node.js toolchain with npm and corepack for the step's `run:` commands. The image ships 24 (active LTS) plus 22 (maintenance LTS) and 25 (current line).

```yaml
- name: build
  uses: buz/setup-node@1.1.0
  with:
    version: stable
    cache: true
  run: |
    npm ci
    npm test
```

## How your commands run

The step's `run:` commands execute after the toolchain setup, in the same shell — everything the template exports (PATH, npm_config_cache, …) is visible to your commands. They start in the step directory: the template declares `default_dir: source`, and a step-level `work_dir` on the step overrides it. The directory must resolve physically inside the workspace.

`version` accepts `stable`/`lts` (= 24), `dev` (= 25), or `22`/`24`/`25`. With `cache: true` the npm cache persists in `<workspace>/.cache/node/npm` across jobs on the same Runner. Each step is an isolated container — pass state between steps through workspace files. Requires a Docker-enabled Runner with egress to the npm registry.

## Versions in image 1.0.0

| `version` | Resolves to |
|-----------|-------------|
| `stable` (default), `lts` | Node.js 24 (active LTS) |
| `dev` | Node.js 25 (current line) |
| `22` | Node.js 22 (maintenance LTS) |

Every run prints the resolved `node --version` as the first log line.

Version 1.0.0 templates remain unchanged and take the historical `script` and `workdir` inputs.
