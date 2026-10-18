# Python build environment

Prepares a pinned Python toolchain (3.14, 3.13, or 3.12) with pip for the step's `run:` commands.

```yaml
- name: test
  uses: buz/setup-python@1.1.0
  with:
    version: stable
    cache: true
  run: |
    pip install -r requirements.txt
    python -m pytest
```

## How your commands run

The step's `run:` commands execute after the toolchain setup, in the same shell — everything the template exports (PATH, PIP_CACHE_DIR, …) is visible to your commands. They start in the step directory: the template declares `default_dir: source`, and a step-level `work_dir` on the step overrides it. The directory must resolve physically inside the workspace.

`version` accepts `stable`/`lts`/`dev` (= 3.14, the newest line in the image) or `3.13`/`3.12`. With `cache: true` the pip cache persists in `<workspace>/.cache/python/pip` across jobs on the same Runner. Each step is an isolated container — pass state between steps through workspace files. Requires a Docker-enabled Runner with egress to pypi.org.

## Versions in image 1.0.0

| `version` | Resolves to |
|-----------|-------------|
| `stable` (default), `lts`, `dev` | Python 3.14 |
| `3.13` | Python 3.13 |
| `3.12` | Python 3.12 |

Every run prints the resolved `python3 --version` as the first log line.

Version 1.0.0 templates remain unchanged and take the historical `script` and `workdir` inputs.
