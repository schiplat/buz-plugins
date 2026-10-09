# Feishu notification

Sends a text message to a Feishu custom-bot group, including available Buz pipeline and job metadata.

```yaml
- name: notify
  uses: buz/feishu@1.0.0
  with:
    webhook: ${secrets.FEISHU_WEBHOOK}
    title: Deployment complete
    content: The release finished successfully.
    at_all: false
```

`webhook` is required and should be stored as a secret. `title` defaults to `Buz job notification`, `content` to empty, and `at_all` to `false`. The step has a 30-second timeout.
