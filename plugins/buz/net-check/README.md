# Network readiness check (HTTP / TCP / UDP)

Polls a service until it is ready — one template for the three checks that used to be spread across `buz/http-check` and `buz/wait-for-tunnel`. Requires `curl` and `nc` (openbsd-netcat) on the runner host.

```yaml
# HTTP status polling (default)
- name: wait for http
  uses: buz/net-check@1.0.0
  with:
    url: http://192.168.39.130:8081/health
    expect_status: 200
    interval: 5s
    attempts: 24

# TCP port probe (tunnel / frp scenarios)
- name: wait for tcp
  uses: buz/net-check@1.0.0
  protocol: tcp
  host: tunnel.example.com
  port: 7000
```

- `protocol` — `http` (default) / `tcp` / `udp`.
- HTTP uses `url` + `expect_status` (+ `insecure` for self-signed TLS).
- TCP/UDP use `host` + `port`.
- `interval` (sleep(1) format, default `5s`) and `attempts` (default `24`) apply to all protocols.

**UDP is best-effort by nature**: UDP has no handshake, so the probe reports whether a datagram was sent without an ICMP port-unreachable — most UDP services never reply to empty probes. Prefer an application-level check (or a template input that triggers a response) when confirmation matters.

Checks run from the Runner host: the polled address must be reachable from the Runner (a LAN target IP, not the target's own 127.0.0.1).
