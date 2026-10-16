# Config fetch

Downloads a configuration bundle (`.tar.gz`) into the workspace and unpacks it — the delivery half of the Config Block flow, for pipelines that keep their config in object storage. Requires `curl` and `tar` on the runner host.

```yaml
- name: fetch config
  uses: buz/config-fetch@1.0.0
  with:
    url: ${secrets.CONFIG_BUNDLE_URL}
    dest: config
```

`url` (masked) is typically a presigned object-storage URL — OSS, S3, MinIO, and R2 all issue them, so no bucket credentials ever appear in the pipeline. `dest` is a relative workspace directory (absolute paths and `..` are rejected). `strip_components` maps to `tar --strip-components`, `max_time` to the curl download timeout.

Pair with a `config.render` block on later steps (render-only mode) to render `.env` files from the unpacked templates.
