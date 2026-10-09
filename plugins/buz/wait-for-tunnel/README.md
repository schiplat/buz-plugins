# TCP tunnel wait

Waits until a TCP endpoint accepts connections, such as a tunnel or a service being brought online.

```yaml
- name: wait for tunnel
  uses: buz/wait-for-tunnel@1.0.0
  with:
    host: tunnel.example.com
    port: 8080
    interval: 5s
    attempts: 60
```

`host` and `port` are required. Defaults are interval `5s`, 60 attempts, and a 10-minute step timeout. This checks TCP connectivity only; it does not verify application readiness or authenticate. The runner must be able to reach the endpoint.
