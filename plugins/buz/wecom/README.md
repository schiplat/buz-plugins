# WeCom notification

Sends a text message to a WeCom (WeChat Work) group bot, including the Buz pipeline name and job URL when available.

```yaml
- name: notify
  uses: buz/wecom@1.0.0
  with:
    webhook: ${secrets.WECOM_WEBHOOK}
    title: Deployment complete
    content: The release finished successfully.
    at_all: false
```

`webhook` is required and should be stored as a secret. `title` defaults to `Buz job notification`, `content` to empty, and `at_all` to `false`. The step has a 30-second timeout.
