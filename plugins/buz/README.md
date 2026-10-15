# Official plugins (`buz/*`)

Templates maintained by the Buz org itself. Every directory here is one
plugin: a `<version>.yaml` step template, a `README.md`, and — for
Docker-engine plugins — an `image/` build context. Community templates live
under their own author namespace, not here.

## What the family covers

| Group | Plugins | Purpose |
|-------|---------|---------|
| Notifications | `feishu`, `dingtalk`, `wecom`, `slack` | Push job results to IM group bots (webhook, masked secret) |
| Artifact upload | `oss-upload`, `s3-upload` | Upload a workspace file to Alibaba Cloud OSS / S3 |
| Readiness & wait | `http-check`, `ssh-wait`, `wait-for-tunnel` | Poll HTTP/TCP/SSH until a deploy target is ready |
| Build toolchains | `setup-rust`, `setup-ruby`, `setup-php`, `setup-lua`, `setup-python`, `setup-node`, `setup-java`, `setup-go` | Run builds/tests inside pinned language toolchains (`stable`/`lts`/`dev` aliases, optional workspace cache) |

## Docker Hub

Docker-engine templates run images published under the
[`schiplat` namespace on Docker Hub](https://hub.docker.com/u/schiplat),
built automatically by CI from the `image/` contexts in this repository:

- Upload tool images: [`buz-plugins-oss-tools`](https://hub.docker.com/r/schiplat/buz-plugins-oss-tools),
  [`buz-plugins-aws-tools`](https://hub.docker.com/r/schiplat/buz-plugins-aws-tools)
- Language toolchains: [`buz-plugins-rust-tools`](https://hub.docker.com/r/schiplat/buz-plugins-rust-tools),
  [`buz-plugins-ruby-tools`](https://hub.docker.com/r/schiplat/buz-plugins-ruby-tools),
  [`buz-plugins-php-tools`](https://hub.docker.com/r/schiplat/buz-plugins-php-tools),
  [`buz-plugins-lua-tools`](https://hub.docker.com/r/schiplat/buz-plugins-lua-tools),
  [`buz-plugins-python-tools`](https://hub.docker.com/r/schiplat/buz-plugins-python-tools),
  [`buz-plugins-node-tools`](https://hub.docker.com/r/schiplat/buz-plugins-node-tools),
  [`buz-plugins-java-tools`](https://hub.docker.com/r/schiplat/buz-plugins-java-tools),
  [`buz-plugins-go-tools`](https://hub.docker.com/r/schiplat/buz-plugins-go-tools)

Specs never reference `:latest` — after CI builds an image, an automation PR
pins the template to an immutable `@sha256:` manifest digest. Images are
Linux `amd64` only; see [plugin-images.md](../../docs/plugin-images.md) for
the build pipeline and
[image-template-conventions.md](../../docs/image-template-conventions.md)
for the authoring rules.

## Using these templates

Manager resolves `uses: buz/<name>@<version>` against the local step index
(resolve & lock). Point the Manager at this repository's `plugins/` directory
(`[step_index].local_dir`, or the default `<yaml_scan_dir>/steps`) and save a
pipeline — the resolved version, content hash, and expanded step JSON are
locked as provenance at save time. Review status comes from
[`reviews.json`](../../reviews.json): every id in this directory carries a
human first review, then CI keeps hashes fresh on green master.
