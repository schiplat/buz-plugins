# Lua runtime

Prepares a pinned Lua interpreter for the step's `run:` commands — `5.4`, `5.3`, or LuaJIT 2.1 (`jit`), all Debian-packaged so interpreter binaries carry upstream signatures.

```yaml
- name: check
  uses: buz/setup-lua@1.1.0
  with:
    version: 5.4
  run: |
    lua -e 'print("hello from", _VERSION)'
```

## How your commands run

The step's `run:` commands execute after the interpreter is placed on PATH, in the same shell — the PATH export is visible to your commands. They start in the step directory: the template declares `default_dir: source`, and a step-level `work_dir` on the step overrides it. The directory must resolve physically inside the workspace.

`version` accepts `stable`/`lts`/`dev` (= 5.4) or `5.3`/`jit`. Lua has no package cache in this image; each step is an isolated container — pass state between steps through workspace files. Requires a Docker-enabled Runner.

## Versions in image 1.0.0

| `version` | Resolves to |
|-----------|-------------|
| `stable` (default), `lts`, `dev` | Lua 5.4 |
| `5.3` | Lua 5.3 |
| `jit` | LuaJIT 2.1 |

Every run prints the resolved interpreter version (`lua -v` / `luajit -v`) as the first log line.

Version 1.0.0 templates remain unchanged and take the historical `script` and `workdir` inputs.
