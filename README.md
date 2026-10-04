# buz-plugins

Official step-template marketplace for [Buz](https://github.com/schiplat/buz) — reusable pipeline steps (notifications, deploy helpers, health checks) referenced from pipelines via `uses:`.

Browse the published catalog at **[plugins.buz.schiplat.com](https://plugins.buz.schiplat.com)** (once deployed).

```yaml
steps:
  - name: notify
    uses: notify/feishu@1.0.0
    with:
      webhook: ${secrets.FEISHU_WEBHOOK}
      title: deploy done
```

## Templates

| Step | Engine | Purpose |
|------|--------|---------|
| `notify/feishu` | shell | Feishu group-bot notification (job link, @all) |
| `notify/dingtalk` | shell | DingTalk group-bot notification (optional HMAC signing) |
| `notify/wecom` | shell | WeCom (WeChat Work) group-bot notification |
| `notify/slack` | shell | Slack incoming webhook |
| `healthcheck/http` | shell | HTTP readiness polling after a deploy |
| `net/wait-for-tunnel` | shell | Wait for a TCP tunnel endpoint (frp/rp scenarios) |
| `deploy/ssh-wait` | shell | Wait for SSH on a target host (after reboot/rebuild) |

All templates are `engine: shell` — pure YAML, no container images required. Docker-toolbox templates (`upload/oss`, `upload/s3`, `docker/prune`, …) are planned but their official images are **not published yet**; they will land once image publishing is set up.

## Use in your Manager

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

## Authoring

One file per template under `plugins/` (`<namespace>-<name>.yaml`, e.g. `notify-feishu.yaml` for id `notify/feishu`). Required fields: `id`, `version` (`X.Y.Z`), `engine`, `run`. Inputs support `type` (string/number/boolean/choice/list), `required`, `default`, `masking`, `pattern`, `options`. Optional fields: `name`, `description`, `description_zh`, `author`, `author_url`, `source_repo`, `keywords`, `publisher` (`official` | `community`), `license`, `default_timeout`.

Community templates must declare `author` and `source_repo` — attribution is part of inclusion.

Validate locally with the same checker CI uses:

```bash
buz-manager step-validate plugins/          # or a single file
```

Rules that matter:

- Values reach `run:` **only** as `INPUT_<UPPER_SNAKE>` env — never reference `${secrets.*}` inside `run:`.
- Mark webhook/credential inputs `masking: true`.
- Non-trivial scripts should move to `engine: docker` with a digest-pinned image once official tool images are published.
- Deployment-type templates must assume manual re-runs (idempotency).
- Ported plugins keep the upstream license/attribution (Apache-2.0 repo, per-file `license:` field).

Environment metadata available to every template: `BUZ_JOB_ID`, `BUZ_JOB_URL`, `BUZ_PIPELINE_NAME`, `BUZ_TEAM`, `BUZ_TRIGGER`, `BUZ_TRIGGERED_BY`, `BUZ_GIT_SHA`, `BUZ_GIT_BRANCH`.

Full spec: marketplace ADR §5 (`docs/design/step-marketplace.md` in the buz repo).

## CI

- **validate**: builds `buz-manager` from source and runs `step-validate plugins/` on every push/PR; also runs `shellcheck` over `scripts/*.sh`.
- **site**: builds the static browse site (`site/` + `index.json` + plugin files + `reviews.json`), uploads it as an artifact, and deploys it to **Cloudflare Pages** on pushes to `master`.

  One-time deploy setup (repo Settings → Secrets and variables → Actions):

  | Secret | Value |
  |--------|-------|
  | `CLOUDFLARE_API_TOKEN` | CF API token with **Cloudflare Pages: Edit** permission |
  | `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account id |

  The first deploy creates the Pages project `buz-plugins`; then bind the custom domain **plugins.buz.schiplat.com** in CF Pages → project → Custom domains.
- **index**: on tags `v*`, generates `index.json` (id / version / sha256 per template) and attaches it to the GitHub release.

## Official review badge

Official templates carry a review record bound to their **content sha256** (`reviews.json`, generated with `scripts/gen_reviews.py` after a maintainer review). Because the badge binds to the hash, any content change invalidates it automatically — a reviewed v1.0 never launders trust for an unreviewed v1.1.

Managers can enforce it:

```toml
[step_index]
reviewed_manifest = "/etc/buz/reviews.json"  # hash → "officially reviewed"
# require_reviewed = true                     # strict: reject unreviewed templates
```

Unreviewed templates resolve with a warning by default; the review status is recorded with each resolution's provenance. The badge means "static lint + manual review at this hash" — not a runtime-safety guarantee.

## Reporting problems

- **Broken / incorrect template** → [open an issue](https://github.com/schiplat/buz-plugins/issues/new?template=report.yml) with the `report` template (step id@version + what happened)
- **Suspected backdoor / malicious behavior** → **do not post details publicly**: use [Private vulnerability reporting](https://github.com/schiplat/buz-plugins/security/advisories/new). Maintainers triage privately, respond within **7 days**, and publish an outcome after handling.

Triage outcomes: benign → closed; violating → template **removed from the index** (takedown) and, when applicable, a note published; fixable → author PR with a version bump (content hash changes, so the review badge auto-invalidates until re-reviewed).

## Namespace note

In Phase 1 (local index) a `uses:` reference is the template `id` plus `@pin` — e.g. `notify/feishu@1.2`. Namespace→index-source bindings (`community/...` pointing at a configured remote index) arrive with Phase 2 `https` indexes.

## License

Apache-2.0 — see [LICENSE](LICENSE).
