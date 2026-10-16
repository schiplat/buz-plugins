# scp (to target host)

Copies one file from the Buz workspace to a target host over SSH/SCP. Runs via `engine: shell` on the Runner — **nothing is installed on the target host**; the only one-time setup is trusting the Runner-side key in the target's `authorized_keys` (a config line, not software).

```yaml
- name: deliver bundle
  uses: buz/scp@1.0.0
  with:
    host: 192.168.39.130
    port: 22
    user: deploy
    ssh_private_key: ${secrets.TARGET_DEPLOY_KEY}
    source: config/configs.tar.gz
    dest: /opt/cella/configs.tar.gz
```

- `ssh_private_key` (masked) — OpenSSH private key; written to a per-step temp file (`0600`, removed on exit), never a CLI argument. Its public key must be in the target user's `authorized_keys`.
- `source` is a relative workspace path (`..` and absolute paths are rejected); `dest` is an absolute path on the target host (parent directories are created via ssh mkdir).
- Key-based auth only — password SCP would require `sshpass` on the Runner (an install we avoid by design).
- `StrictHostKeyChecking=accept-new`: the target's host key is trusted on first contact; provision known hosts for stricter verification.

Pair with [`buz/config-fetch`](../config-fetch/README.md) / [`buz/oss-download`](../oss-download/README.md) (Runner-side download) to move artifacts onto deploy targets — e.g. download a config bundle from OSS, scp it to the target, then `config.render` (render-only) and `docker compose up` there.
