# DingTalk notification

Sends a text message to a DingTalk custom-bot group. Pipeline name and job URL are included when Buz provides them.

```yaml
- name: notify
  uses: buz/dingtalk@1.0.0
  with:
    webhook: ${secrets.DINGTALK_WEBHOOK}
    secret: ${secrets.DINGTALK_SECRET} # optional HMAC signing secret
    title: Deployment complete
    content: The release finished successfully.
    at_all: false
```

`webhook` is required. `secret` is optional; `title` defaults to `Buz job notification`, `content` to empty, and `at_all` to `false`. Store the webhook and signing secret as secrets. The step has a 30-second timeout.
