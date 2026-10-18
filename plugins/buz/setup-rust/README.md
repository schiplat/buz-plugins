# Rust build environment

Prepares a pinned Rust toolchain (cargo/rustc) for the step's `run:` commands. The image ships the stable toolchain — **Rust 1.99 at image 1.0.0**, frozen at image build time; `dev`/`nightly` selects the nightly channel and any `X.Y` (for example `1.85`) installs that release via rustup at run time.

```yaml
- name: build
  uses: buz/setup-rust@1.1.0
  with:
    version: stable
    cache: true
  run: |
    cargo test --locked
    cargo build --release
```

## How your commands run

The step's `run:` commands execute after the toolchain setup, in the same shell — everything the template exports (CARGO_HOME, PATH, …) is visible to your commands. They start in the step directory: the template declares `default_dir: source`, and a step-level `work_dir` on the step overrides it. The directory must resolve physically inside the workspace.

## Versions in image 1.0.0

| `version` | Resolves to |
|-----------|-------------|
| `stable` (default), `lts` | **Rust 1.99** (stable channel, frozen at build) |
| `dev`, `nightly` | nightly channel, installed via rustup at run time |
| `X.Y` (e.g. `1.85`) | that release, installed via rustup at run time |

Every run prints the resolved `rustc --version` as the first log line. A rebuild of the image moves `stable` to the then-current release and bumps the template version.

`cache: true` persists the cargo registry and any on-demand installed toolchains in `<workspace>/.cache/rust` and is reused by later jobs on the same Runner. Each step is an isolated container — pass state between steps through workspace files. Requires a Docker-enabled Runner with egress to crates.io/static.rust-lang.org.

Version 1.0.0 templates remain unchanged and take the historical `script` and `workdir` inputs.
