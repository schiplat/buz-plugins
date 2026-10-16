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
| `buz/oss-upload` | docker | Upload a workspace file to Alibaba Cloud OSS with ossutil v2 |
| `buz/s3-upload` | docker | Upload a workspace file to S3 with AWS CLI v2 |
| `buz/archive` | shell | Pack workspace paths into a tar.gz with sha256 checksum |
| `buz/docker-compose` | ssh | Deploy a Docker Compose project on the target host (Buz 1.7.5+) |
| `buz/docker` | docker | Build and push an OCI image from a workspace context (requires the host Docker socket) |
| `buz/docker-login` | shell/ssh | Registry login — Runner host by default, or target hosts via `engine: ssh` (pair with `buz/docker-logout`) |
| `buz/docker-logout` | shell | Best-effort registry logout on the Runner host |
| `buz/config-fetch` | shell/ssh | Download + unpack a config bundle (presigned OSS/S3/MinIO/R2 URL, optional Basic/header auth) — Runner workspace or target hosts via `engine: ssh` |
| `buz/git-clone` | shell | Clone a Git repository into the workspace (shallow, token auth) |
| `buz/webhook-notify` | shell | Generic JSON webhook notifications with job metadata |
| `buz/k8s-apply` | shell | Apply workspace manifests to Kubernetes with kubectl |
| `buz/helm-upgrade` | shell | Helm upgrade --install from a workspace chart |
| `buz/setup-rust` | docker | Rust build environment: pinned toolchain, on-demand rustup install, optional cargo cache |
| `buz/setup-ruby` | docker | Ruby build environment (3.4/3.3) with gem/bundler caching |
| `buz/setup-php` | docker | PHP build environment (8.4/8.3) with Composer and its cache |
| `buz/setup-lua` | docker | Lua interpreter 5.4 / 5.3 / LuaJIT 2.1 (Debian-packaged) |
| `buz/setup-python` | docker | Python build environment (3.14/3.13/3.12) with pip caching |
| `buz/setup-node` | docker | Node.js build environment (24/22 LTS) with npm caching |
| `buz/setup-java` | docker | Java build environment (Temurin JDK 21/25/17) with Gradle cache support |
| `buz/setup-go` | docker | Go build environment (1.26/1.25) with module/build caching |

Each `buz/setup-*` step executes its `script` input in the selected toolchain from a `workdir` inside the workspace; every step is an isolated container, so state travels between steps via workspace files, not the environment. With `cache: true` the package-manager cache lives under `<workspace>/.cache/` and is reused by later jobs on the same Runner. Builds download dependencies from the language ecosystems (crates.io, rubygems.org, packagist.org, PyPI, the npm registry, Maven Central, the Go module proxy, …); make sure Runner egress policy allows the endpoints your build needs. Template authoring conventions for image-backed plugins: [docs/image-template-conventions.md](docs/image-template-conventions.md).

Docker templates require a Docker-enabled Runner and Linux `amd64` tool images that have been published and digest-pinned. Changes to an image's build context or its own YAML template automatically publish only that image from `master`; after a successful build, the workflow opens or updates a family-specific PR to pin its template to the published digest. See [image build, publishing, and runtime requirements](docs/plugin-images.md) for the optional `BUZ_PLUGIN_GITHUB_PR_TOKEN` needed to trigger CI on generated PRs. The upload templates are currently `1.0.2`; use their digest-pinned references for production.

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

Save a pipeline referencing a step — the Manager validates `with:` against the template inputs, expands the step, and locks version + content hash. Before saving it, you can check `uses:` resolution and input validation without executing steps using the Buz Manager plan command:

```bash
buz-manager pipeline plan examples/plugin-uses-dry-run.yml \
  --step-index ./plugins \
  --reviews ./reviews.json \
  --require-reviewed
```

The example includes both Shell and digest-pinned Docker templates. Planning prints resolved versions and template hashes, but never executes commands or reveals input/secret values. By default it makes a read-only registry manifest request for Docker tags/digests; it does not pull or run images. `not found` fails the command, while private images without credentials and network/registry errors are reported as `unverified`. Add `--offline` to skip those requests. This does not prove an image is pullable by your Runner or that the step will run successfully. The plan also does not check that Manager Secrets or Variables exist or that a Runner is available. See the [Buz pipeline planning guide](https://github.com/schiplat/buz/blob/master/docs/content/docs/01-architecture/authoring/pipeline-format.md#plan-a-pipeline-without-executing-it). Once saved, the Manager locks the resolved template version and hash so upstream changes do not alter an existing pipeline.

## Authoring

Step specs use `plugins/<namespace>/<name>/<version>.yaml` (for example `plugins/buz/feishu/1.0.0.yaml`). The namespace/name path follows the canonical step ID; multiple versions may coexist, and only YAML files are indexed. Every plugin directory must ship a non-empty `README.md` documenting the step's purpose, inputs, and a usage example — CI enforces this (`scripts/check_plugin_readmes.py`). Plugin names use a single technology noun (`docker`, `docker-compose`, `archive`, `setup-<lang>`, `feishu`) rather than verb phrases — the pipeline context supplies the verb. Governance and trust model — what the marketplace certifies, the official/community tiers, and the ssh engine policy: [docs/governance.md](docs/governance.md). Plugin-specific Docker build assets belong alongside that plugin in an `image/` subdirectory and are not scanned as templates. The canonical ID format is `<namespace>/<name>` (for example `buz/feishu`); optional `category` metadata is separate and never part of the ID. The `id` field is the canonical identity everywhere: use the complete ID in `uses:`, review commands, issues, and provenance. `@version` belongs on pipeline `uses:` references, while issue/review identifiers should use the ID itself (the issue title includes `@version` where useful). Required fields: `id`, `version` (`X.Y.Z`), `engine`, `run`. Inputs support `type` (string/number/boolean/choice/list), `required`, `default`, `masking`, `pattern`, `options`. Optional fields: `name`, `category`, `description`, `description_zh`, `author`, `author_url`, `source_repo`, `keywords`, `publisher` (`official` | `community`), `license`, `default_timeout`.

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

- **validate**: downloads the `buz-manager` binary from the private buz release (no Rust toolchain, no source build) and runs `step-validate` on the recursively discovered YAML file list on every push/PR; also runs `shellcheck` over `scripts/*.sh`. `BUZ_REPO_PAT_V2` must be configured with read access to `schiplatv2/buz`; if absent, validation fails explicitly. GitHub does not expose repository secrets to fork PRs, so fork contributors need a maintainer-run validation or a branch within the repository before merge; required checks must not be treated as passing when validation is skipped.

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

- **Official (`buz/*`) — human first review, CI tracking after.** A brand-new official template is never auto-blessed: once a maintainer reviews the exact file contents, the id is recorded with the same manual command community templates use (`scripts/gen_reviews.py --date <d> --commit <sha> buz/<name>`). From then on CI keeps every version of that id fresh on green master — `step-validate` + `lint_runs` + the egress allowlist must pass for the exact content hash, and the allowlist itself is part of review, not a build fix. CI regenerates ci-source entries on every push to `master` (`scripts/gen_reviews.py --auto`) and commits the refreshed manifest.
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

In Phase 1 (local index) a `uses:` reference is the complete template `id` plus `@version` — e.g. `buz/feishu@1.2.0`. The index `file` value is a repository-relative POSIX path (for example `plugins/buz/feishu/1.0.0.yaml`); consumers should resolve it relative to the index/repository root, never depend on an absolute build-machine path. Namespace→index-source bindings (`community/...` pointing at a configured remote index) arrive with Phase 2 `https` indexes.

## License

Apache-2.0 — see [LICENSE](LICENSE).
