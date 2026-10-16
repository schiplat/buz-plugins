# Alibaba Cloud OSS download

Downloads one object from an Alibaba Cloud OSS bucket into the Buz workspace using ossutil v2 — the download counterpart of [`buz/oss-upload`](../oss-upload/README.md). Typical use: pull a config bundle produced by a release, then render it with a `config.render` block (render-only).

```yaml
- name: download config bundle
  uses: buz/oss-download@1.0.0
  with:
    endpoint: https://oss-cn-hangzhou.aliyuncs.com
    region: cn-hangzhou
    bucket: release-artifacts
    object: config_tpl/app/1.0.0/configs.tar.gz
    dest: config/configs.tar.gz
    access_key_id: ${secrets.OSS_ACCESS_KEY_ID}
    access_key_secret: ${secrets.OSS_ACCESS_KEY_SECRET}
    session_token: ${secrets.OSS_SESSION_TOKEN} # optional
```

All inputs except `session_token` are required. Both key inputs are masked; use an HTTPS endpoint and least-privilege or short-lived credentials.

Dual engine (`engines: [docker, ssh]`):

- **`engine: docker` (default)** — `dest` is **relative** to the Buz workspace (downloaded into the Runner workspace).
- **`engine: ssh`** — the download runs **on the target hosts** (`host:` list); `dest` must be an **absolute** path on each host, so the bundle lands exactly where later ssh steps (render, compose) need it. Prerequisite: the `ossutil` binary installed once on each target host (binary only — credentials arrive per-step as masked env, nothing is stored on the host).

A Docker-enabled Linux `amd64` runner is required. The template runs the same digest-pinned `buz-plugins-oss-tools` image as `buz/oss-upload`; after a successful image build, the release workflow opens a PR to pin the published digest — do not use it in production until that PR is merged. Default timeout: 10 minutes.

For unattended authenticated downloads of generic HTTP resources (non-OSS), prefer [`buz/config-fetch`](../config-fetch/README.md) with a presigned URL, Basic auth, or headers.
