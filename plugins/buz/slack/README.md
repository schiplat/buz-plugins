# Slack notification

Posts a message to a Slack channel through an incoming webhook. Buz pipeline name and job URL are appended when available.

```yaml
- name: notify
  uses: buz/slack@1.0.0
  with:
    webhook: ${secrets.SLACK_WEBHOOK}
    title: Deployment complete
    content: The release finished successfully.
```

`webhook` is required and should be stored as a secret. `title` defaults to `Buz job notification` and `content` to empty. The step has a 30-second timeout.
