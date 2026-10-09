# S3 upload

Uploads one file from the Buz workspace to an S3 bucket using AWS CLI v2.

```yaml
- name: upload artifact
  uses: buz/s3-upload@1.0.2
  with:
    source: dist/app.tar.gz
    bucket: release-artifacts
    key: app/app.tar.gz
    region: us-east-1
    access_key_id: ${secrets.AWS_ACCESS_KEY_ID}
    secret_access_key: ${secrets.AWS_SECRET_ACCESS_KEY}
    endpoint_url: https://s3.us-east-1.amazonaws.com
    session_token: ${secrets.AWS_SESSION_TOKEN} # optional
```

All inputs except `session_token` are required. `source` must be a readable path inside the Buz workspace; `endpoint_url` must use HTTPS and be reachable from the runner. Prefer least-privilege, short-lived credentials. A Docker-enabled Linux `amd64` runner is required. After a successful image build, the release workflow opens a PR to pin this template to the published digest; do not use it in production until that PR is merged. Default timeout: 10 minutes.
