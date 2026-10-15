# Generic webhook notification

POSTs a JSON message (`{"text": "…"}`) to any HTTPS webhook endpoint, with
Buz job metadata appended automatically. Use it for notification targets
without a dedicated plugin (Zulip, Gotify, ntfy, Discord-compatible
catch-alls, in-house receivers).

```yaml
steps:
  - name: Notify
    uses: buz/webhook-notify@1.0.0
    with:
      url: ${secrets.DEPLOY_WEBHOOK}
      title: deploy done
      content: app 1.2.0 is live
```

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `url` | string | yes | — | Webhook endpoint URL (masked) |
| `title` | string | no | `Buz job notification` | Message title / first line |
| `content` | string | no | — | Extra message body appended under the title |

## Notes

- The payload shape is `{"text": "…"}` — targets expecting a different
  envelope (Slack has `buz/slack`, Feishu `buz/feishu`) should use their
  dedicated plugins instead.
- Store the URL as a Manager Secret and reference it via `${secrets.*}`.
- Engine: shell (runs on the Runner host). Egress to the webhook host must
  be allowed by the Runner policy; the URL is declared in the reviewed
  egress baseline.
