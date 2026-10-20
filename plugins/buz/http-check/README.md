# HTTP / TCP / UDP check

Polls a service until it is ready — one check template that covers HTTP status polling, TCP port probes, and best-effort UDP — the TCP cases that used to need `buz/wait-for-tunnel` are built in. Requires `curl` and `nc` (openbsd-netcat) on the runner host.

```yaml
# HTTP status polling (default)
- name: wait for http
  uses: buz/http-check@1.0.0
  with:
    url: http://192.0.2.10:8081/health
    expect_status: 200
    interval: 5s
    attempts: 24

# TCP port probe (tunnel / frp scenarios)
- name: wait for tcp
  uses: buz/http-check@1.0.0
  protocol: tcp
  host: tunnel.example.com
  port: 7000

# HTTP with Basic auth (1.1.0+)
- name: wait for http (authenticated)
  uses: buz/http-check@1.1.0
  with:
    url: https://service.example.com/health
    username: ${secrets.HEALTH_USER}
    password: ${secrets.HEALTH_PASSWORD}
    expect_status: 200
```

## Inputs

| Input | Protocol | Description |
|---|---|---|
| `protocol` | all | `http` (default) / `tcp` / `udp` — selects which other inputs apply |
| `url` | http | URL to poll — **required for http** |
| `expect_status` | http | Expected status code (default `200`) |
| `insecure` | http | Skip TLS verification (default `false`) |
| `username` | http (1.1.0+) | HTTP Basic auth username — set together with `password` |
| `password` | http (1.1.0+) | HTTP Basic auth password (masked; delivered via a curl config file, never a CLI argument) |
| `host` | tcp/udp | Target host — **required for tcp/udp** |
| `port` | tcp/udp | Target port |
| `interval` | all | Sleep between attempts (sleep(1) format, default `5s`) |
| `attempts` | all | Total attempts before failing (default `24`) |

**UDP is best-effort by nature**: UDP has no handshake, so the probe reports whether a datagram was sent without an ICMP port-unreachable — most UDP services never reply to empty probes. Prefer an application-level check (or a template input that triggers a response) when confirmation matters.

Checks run from the Runner host: the polled address must be reachable from the Runner (a LAN target IP, not the target's own 127.0.0.1).
