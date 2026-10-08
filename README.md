# buz-plugins

Official step-template marketplace for [Buz](https://github.com/schiplat/buz) — reusable pipeline steps (notifications, deploy helpers, health checks) referenced from pipelines via `uses:`.

Browse the published catalog at **[plugins.buz.schiplat.com](https://plugins.buz.schiplat.com)** (once deployed).

```yaml
steps:
  - name: notify
    uses: buz/feishu@1.0.0
    with:
      webhook: ${secrets.FEISHU_WEBHOOK}
      title: deploy done
```

## Templates

| Step | Engine | Purpose |
|------|--------|---------|
| `buz/feishu` | shell | Feishu group-bot notification (job link, @all) |
| `buz/dingtalk` | shell | DingTalk group-bot notification (optional HMAC signing) |
| `buz/wecom` | shell | WeCom (WeChat Work) group-bot notification |
| `buz/slack` | shell | Slack incoming webhook |
| `buz/http-check` | shell | HTTP readiness polling after a deploy |
| `buz/wait-for-tunnel` | shell | Wait for a TCP tunnel endpoint (frp/rp scenarios) |
| `buz/ssh-wait` | shell | Wait for SSH on a target host (after reboot/rebuild) |

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

One file per template under `plugins/` (`<namespace>-<name>.yaml`, e.g. `buz-feishu.yaml` for id `buz/feishu`). The canonical ID format is `<namespace>/<name>` (for example `buz/feishu`); optional `category` metadata is separate and never part of the ID. The `id` field is the canonical identity everywhere: use the complete ID in `uses:`, review commands, issues, and provenance. `@version` belongs on pipeline `uses:` references, while issue/review identifiers should use the ID itself (the issue title includes `@version` where useful). Required fields: `id`, `version` (`X.Y.Z`), `engine`, `run`. Inputs support `type` (string/number/boolean/choice/list), `required`, `default`, `masking`, `pattern`, `options`. Optional fields: `name`, `category`, `description`, `description_zh`, `author`, `author_url`, `source_repo`, `keywords`, `publisher` (`official` | `community`), `license`, `default_timeout`.

Community templates must declare `author` and `source_repo` — attribution is part of inclusion.

`source_repo` is the canonical HTTPS URL for the template's source, preferably a direct URL to the exact template file in its source repository. Use a commit-pinned URL when an immutable reference is needed. Official templates must also set it so the marketplace can link users from both the detail dialog and the crawlable static detail page. Avoid pointing only to a generic project homepage when a direct file URL is available. The site build checks that every official template has a valid HTTPS `source_repo` and that each generated detail page renders the matching link.

For community templates, `author_url` should link to the author's profile or organization page; `source_repo` should link to the actual source file/repository. Keep these attribution fields in sync when moving or renaming a source file.

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

- **validate**: downloads the `buz-manager` binary from the private buz release (no Rust toolchain, no source build) and runs `step-validate plugins/` on every push/PR; also runs `shellcheck` over `scripts/*.sh`. `BUZ_REPO_PAT_V2` must be configured with read access to `schiplatv2/buz`; if absent, validation fails explicitly. GitHub does not expose repository secrets to fork PRs, so fork contributors need a maintainer-run validation or a branch within the repository before merge; required checks must not be treated as passing when validation is skipped.

  Optional version pin — repo Settings → Secrets and variables → Actions → **Variables** tab:

  | Variable | Value |
  |----------|-------|
  | `BUZ_VERSION` | Release tag to validate against (e.g. `v1.7.0`). Empty → latest release. |
- **site**: builds the static browse site in an unprivileged read-only job and uploads it as an artifact. A separate publish job only runs on trusted pushes to `master`, then deploys to Cloudflare Pages if credentials are configured and persists the refreshed official review manifest.

  One-time deploy setup (repo Settings → Secrets and variables → Actions):

  | Secret | Value |
  |--------|-------|
  | `CLOUDFLARE_API_TOKEN` | CF API token with **Cloudflare Pages: Edit** permission |
  | `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account id |

  The first deploy creates the Pages project `buz-plugins`; then bind the custom domain **plugins.buz.schiplat.com** in CF Pages → project → Custom domains.
- **index**: on tags `v*`, generates `index.json` (id / version / sha256 per template) and attaches it to the GitHub release.

## Review badges

Every entry in `reviews.json` binds a review to a **content sha256** — any content change invalidates the badge automatically, so a reviewed v1.0 never launders trust for an unreviewed v1.1. The two namespaces carry different trust models:

- **Official (`buz/*`) — CI-issued.** The same org writes and reviews these templates, so a human sign-off adds no independent signal. Instead green CI is the gate: `step-validate` + `lint_runs` + the egress allowlist (`egress-allowlist.json`) must all pass for the exact content hash. CI regenerates these entries on every push to `master` (`scripts/gen_reviews.py --auto`) and commits the refreshed manifest. A deviation from the egress baseline fails the build — updating the allowlist is part of review, not a build fix.
- **Community (`<author>/…`) — human-issued.** CI green is a prerequisite, never a substitute: a maintainer reviews the PR on GitHub, then records the entry using the canonical full ID from the YAML/index, e.g. `scripts/gen_reviews.py --date <d> --commit <sha> buz/telegram`. Manual invocation upserts the selected current content review and preserves unrelated review records.

Managers can enforce it:

```toml
[step_index]
reviewed_manifest = "/etc/buz/reviews.json"  # hash → "officially reviewed"
# require_reviewed = true                     # strict: reject unreviewed templates
```

Unreviewed templates resolve with a warning by default; the review status is recorded with each resolution's provenance. The badge means "static lint + manual review at this hash" — not a runtime-safety guarantee.

## Reporting problems

- **Broken / incorrect template** → [open an issue](https://github.com/schiplat/buz-plugins/issues/new?template=report.yml) with the canonical full step ID (including `buz/` for official steps) and version, e.g. `buz/feishu@1.0.0`
- **Suspected backdoor / malicious behavior** → **do not post details publicly**: use [Private vulnerability reporting](https://github.com/schiplat/buz-plugins/security/advisories/new). Maintainers triage privately, respond within **7 days**, and publish an outcome after handling.

Triage outcomes: benign → closed; violating → template **removed from the index** (takedown) and, when applicable, a note published; fixable → author PR with a version bump (content hash changes, so the review badge auto-invalidates until re-reviewed).

## Namespace note

In Phase 1 (local index) a `uses:` reference is the complete template `id` plus `@version` — e.g. `buz/feishu@1.2.0`. The index `file` value is a repository-relative POSIX path (for example `plugins/buz-feishu.yaml`); consumers should resolve it relative to the index/repository root, never depend on an absolute build-machine path. Namespace→index-source bindings (`community/...` pointing at a configured remote index) arrive with Phase 2 `https` indexes.

## License

Apache-2.0 — see [LICENSE](LICENSE).
