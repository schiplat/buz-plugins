# Rust build environment

Runs POSIX `script` commands inside a pinned Rust toolchain (cargo/rustc). The image ships the stable toolchain — **Rust 1.99 at image 1.0.0**, frozen at image build time; `dev`/`nightly` selects the nightly channel and any `X.Y` (for example `1.85`) installs that release via rustup at run time.

```yaml
- name: build
  uses: buz/setup-rust@1.0.0
  with:
    version: stable
    cache: true
    workdir: service-api
    script: |
      cargo test --locked
      cargo build --release
```

## Versions in image 1.0.0

| `version` | Resolves to |
|-----------|-------------|
| `stable` (default), `lts` | **Rust 1.99** (stable channel, frozen at build) |
| `dev`, `nightly` | nightly channel, installed via rustup at run time |
| `X.Y` (e.g. `1.85`) | that release, installed via rustup at run time |

Every run prints the resolved `rustc --version` as the first log line. A rebuild of the image moves `stable` to the then-current release and bumps the template version.

`cache: true` persists the cargo registry in `<workspace>/.cache/rust/cargo` and is reused by later jobs on the same Runner. Each step is an isolated container — pass state between steps through workspace files. Requires a Docker-enabled Runner with egress to crates.io/static.rust-lang.org.
