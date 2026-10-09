# SSH wait

Waits for an SSH server to accept a login, for example after a host reboot or rebuild. It runs from the runner host and uses the runner's SSH configuration and credentials.

```yaml
- name: wait for server
  uses: buz/ssh-wait@1.0.0
  with:
    host: server.example.com
    port: 22
    user: deploy
    interval: 10s
    attempts: 60
```

`host` is required. Defaults are port `22`, user `root`, interval `10s`, 60 attempts, and a 15-minute step timeout. SSH uses batch mode and accepts a host key on first contact (`StrictHostKeyChecking=accept-new`); provision trusted host keys when stronger host identity verification is required.
