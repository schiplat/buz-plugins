# Ruby build environment

Prepares a pinned Ruby toolchain (3.4 or 3.3) with gem/bundler for the step's `run:` commands. Ruby 3.3 is EOL upstream and kept only for existing applications.

```yaml
- name: test
  uses: buz/setup-ruby@1.1.0
  with:
    version: stable
    cache: true
  run: |
    bundle install
    bundle exec rake test
```

## How your commands run

The step's `run:` commands execute after the toolchain setup, in the same shell — everything the template exports (PATH, GEM_HOME, BUNDLE_PATH, …) is visible to your commands. They start in the step directory: the template declares `default_dir: source`, and a step-level `work_dir` on the step overrides it. The directory must resolve physically inside the workspace.

`version` accepts `stable`/`lts`/`dev` (= 3.4, the newest line in the image) or `3.3`. With `cache: true`, gems and the bundler path persist in `<workspace>/.cache/ruby` across jobs on the same Runner. Each step is an isolated container — pass state between steps through workspace files. Requires a Docker-enabled Runner with egress to rubygems.org.

## Versions in image 1.0.0

| `version` | Resolves to |
|-----------|-------------|
| `stable` (default), `lts`, `dev` | Ruby 3.4 |
| `3.3` | Ruby 3.3 (EOL upstream, kept for existing apps) |

Every run prints the resolved `ruby --version` as the first log line.

Version 1.0.0 templates remain unchanged and take the historical `script` and `workdir` inputs.
