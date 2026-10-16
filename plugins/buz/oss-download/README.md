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

All inputs except `session_token` are required. `dest` must be a relative path inside the Buz workspace (parent directories are created); `..` and absolute paths are rejected. Use an HTTPS endpoint and least-privilege or short-lived credentials — both key inputs are masked.

A Docker-enabled Linux `amd64` runner is required. The template runs the same digest-pinned `buz-plugins-oss-tools` image as `buz/oss-upload`; after a successful image build, the release workflow opens a PR to pin the published digest — do not use it in production until that PR is merged. Default timeout: 10 minutes.

For unattended authenticated downloads of generic HTTP resources (non-OSS), prefer [`buz/config-fetch`](../config-fetch/README.md) with a presigned URL, Basic auth, or headers.
