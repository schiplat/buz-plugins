# buz-plugins

Official step-template index for [Buz](https://github.com/schiplat/buz) — reusable pipeline steps (notifications, deploy helpers, health checks) referenced from pipelines via `uses:`.

Buz 官方步骤模板库：通过 `uses:` 在流水线里引用可复用步骤（通知、部署辅助、健康检查）。

```yaml
steps:
  - name: notify
    uses: notify/feishu@1.0.0
    with:
      webhook: ${secrets.FEISHU_WEBHOOK}
      title: deploy done
```

## First batch / 首批

| Step | Engine | Purpose |
|------|--------|---------|
| `notify/feishu` | shell | 飞书群机器人通知（附任务链接、@全员） |
| `notify/dingtalk` | shell | 钉钉群机器人通知（支持加签） |
| `notify/wecom` | shell | 企业微信群机器人通知 |
| `notify/slack` | shell | Slack incoming webhook |
| `healthcheck/http` | shell | 部署后 HTTP 就绪轮询 |
| `net/wait-for-tunnel` | shell | 等待 TCP 隧道端点连通（frp/rp 场景） |
| `deploy/ssh-wait` | shell | 等待目标机 SSH 可登录（重启/重装后） |

All templates are `engine: shell` — pure YAML, no container images required. Docker-toolbox templates (`upload/oss`, `upload/s3`, `docker/prune`, …) are planned but their official images are **not published yet**; they will land once image publishing is set up.

所有模板均为 shell 引擎——纯 YAML 分发，不依赖任何容器镜像。工具箱类插件（upload/oss、docker/prune 等）待镜像发布渠道就绪后再落地。

## Use in your Manager / 在 Manager 中使用

Buz resolves `uses:` against a **local step index** at pipeline-save time (resolve & lock — provenance is stored per pipeline):

```bash
# Option A: default location — clone this repo's plugins/ into the scan dir
git clone https://github.com/schiplat/buz-plugins.git
sudo cp -r buz-plugins/plugins /opt/buz/pipelines/steps

# Option B: point the Manager at any directory
#   manager.toml
#   [step_index]
#   local_dir = "/etc/buz/steps"
```

Save a pipeline referencing a step — the Manager validates `with:` against the template inputs, expands the step, and locks version + content hash. Upstream tag moves never change an already-saved pipeline.

保存引用模板的流水线时，Manager 会校验 `with:` 输入、展开步骤并锁定版本与内容哈希；上游更新不影响已保存的流水线。

## Authoring / 贡献模板

One file per template under `plugins/` (`<namespace>-<name>.yaml`, e.g. `notify-feishu.yaml` for id `notify/feishu`). Required fields: `id`, `version` (`X.Y.Z`), `engine`, `run`. Inputs support `type` (string/number/boolean/choice/list), `required`, `default`, `masking`, `pattern`, `options`.

Validate locally with the same checker CI uses:

```bash
buz-manager step-validate plugins/          # or a single file
```

Rules that matter / 关键纪律:

- Values reach `run:` **only** as `INPUT_<UPPER_SNAKE>` env — never reference `${secrets.*}` inside `run:`.
- Mark webhook/credential inputs `masking: true`.
- Non-trivial scripts should move to `engine: docker` with a digest-pinned image once official tool images are published.
- Deployment-type templates must assume manual re-runs (idempotency).
- Ported plugins keep the upstream license/attribution (Apache-2.0 repo, per-file `license:` field).

Environment metadata available to every template: `BUZ_JOB_ID`, `BUZ_JOB_URL`, `BUZ_PIPELINE_NAME`, `BUZ_TEAM`, `BUZ_TRIGGER`, `BUZ_TRIGGERED_BY`, `BUZ_GIT_SHA`, `BUZ_GIT_BRANCH`.

Full spec: marketplace ADR §5 (`docs/design/step-marketplace.md` in the buz repo).

## CI

- **validate**: builds `buz-manager` from source and runs `step-validate plugins/` on every push/PR; also runs `shellcheck` over `scripts/*.sh`.
- **index**: on tags `v*`, generates `index.json` (id / version / sha256 per template) and attaches it to the GitHub release. The Phase 2 static browse site (`plugins.buz.schiplat.com`) is built from the same file.

## Namespace note

In Phase 1 (local index) a `uses:` reference is the template `id` plus `@pin` — e.g. `notify/feishu@1.2`. Namespace→index-source bindings (`community/...` pointing at a configured remote index) arrive with Phase 2 `https` indexes.

## License

Apache-2.0 — see [LICENSE](LICENSE).
