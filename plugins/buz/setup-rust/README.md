# Rust build environment

Runs POSIX `script` commands inside a pinned Rust toolchain (cargo/rustc). The image ships the stable toolchain; `dev`/`nightly` selects the nightly channel and any `X.Y` (for example `1.85`) installs that release via rustup at run time.

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

`version` accepts `stable` (default), `lts` (= stable), `dev`/`nightly`, or an `X.Y` release; `workdir` is relative to the workspace root. With `cache: true` the cargo registry persists in `<workspace>/.cache/rust/cargo` and is reused by later jobs on the same Runner. Each step is an isolated container — pass state between steps through workspace files. Requires a Docker-enabled Runner with egress to crates.io/static.rust-lang.org.
