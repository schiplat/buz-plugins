# Node.js build environment

Runs POSIX `script` commands inside a pinned Node.js toolchain with npm and corepack. The image ships 24 (active LTS) plus 22 (maintenance LTS) and 25 (current line).

```yaml
- name: build
  uses: buz/setup-node@1.0.0
  with:
    version: stable
    cache: true
    script: |
      npm ci
      npm test
```

`version` accepts `stable`/`lts` (= 24), `dev` (= 25), or `22`/`24`/`25`. With `cache: true` the npm cache persists in `<workspace>/.cache/node/npm` across jobs on the same Runner. Each step is an isolated container — pass state between steps through workspace files. Requires a Docker-enabled Runner with egress to the npm registry.
