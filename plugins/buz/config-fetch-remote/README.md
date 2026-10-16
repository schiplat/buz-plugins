# Config fetch (deploy target hosts)

Downloads a configuration bundle (`.tar.gz`) on the deploy target hosts and unpacks it — the delivery half of the Config Block flow when the config lives in object storage. Runs via `engine: ssh`: set the step-level `host:` list. Requires `curl` and `tar` on the target hosts, and **egress from the target hosts to the storage endpoint** (gz-style hosts that already pull images from the same cloud usually have this).

```yaml
- name: fetch config
  uses: buz/config-fetch-remote@1.0.0
  host:
    - web-01
  with:
    url: ${secrets.CONFIG_BUNDLE_URL}
    dest: /opt/app
```

`url` (masked) is typically a presigned object-storage URL — OSS, S3, MinIO, and R2 all issue them, so no bucket credentials ever appear in the pipeline; refresh it per deploy (`ossutil sign oss://<bucket>/<key>` / `aws s3 presign ... --expires-in 3600`). `dest` must be an **absolute path on the target host**. `strip_components` maps to `tar --strip-components`, `max_time` to the curl download timeout.

Pair with a `config.render` block on later ssh steps (render-only mode): templates are fetched back to the Runner, rendered with job secrets (secrets never leave the Runner), and the outputs are uploaded — so the fetch step only needs to place templates on the target host.
