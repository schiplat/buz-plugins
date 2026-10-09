# Alibaba Cloud OSS upload

Uploads one file from the Buz workspace to an Alibaba Cloud OSS bucket using ossutil v2.

```yaml
- name: upload artifact
  uses: buz/oss-upload@1.0.1
  with:
    source: dist/app.tar.gz
    bucket: release-artifacts
    object: app/app.tar.gz
    endpoint: https://oss-cn-hangzhou.aliyuncs.com
    region: cn-hangzhou
    access_key_id: ${secrets.OSS_ACCESS_KEY_ID}
    access_key_secret: ${secrets.OSS_ACCESS_KEY_SECRET}
    session_token: ${secrets.OSS_SESSION_TOKEN} # optional
```

All inputs except `session_token` are required. `source` must be a readable path inside the Buz workspace; use an HTTPS endpoint and least-privilege or short-lived credentials. A Docker-enabled Linux `amd64` runner is required. After a successful image build, the release workflow opens a PR to pin this template to the published digest; do not use it in production until that PR is merged. Default timeout: 10 minutes.
