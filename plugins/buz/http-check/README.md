# HTTP check

Polls a URL until it returns the expected HTTP status, useful for waiting for a deployed service to become ready.

```yaml
- name: wait for service
  uses: buz/http-check@1.0.0
  with:
    url: https://service.example.com/health
    expect_status: 200
    interval: 5s
    attempts: 24
```

`url` is required. Defaults are status `200`, interval `5s`, 24 attempts, and a 5-minute step timeout. Set `insecure: true` only when intentionally skipping TLS certificate verification. The runner must be allowed to reach the target URL.
