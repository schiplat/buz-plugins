# buz-plugins

Official step-template marketplace for [Buz](https://github.com/schiplat/buz) — reusable pipeline steps (notifications, deploy helpers, health checks) referenced from pipelines via `uses:`.

Browse the published catalog at **[plugins.buz.schiplat.com](https://plugins.buz.schiplat.com)** — every plugin's purpose, inputs, masking, engines, and a usage example live on its catalog page; this README deliberately does not list them (the catalog is generated from the index and never drifts from it).

```yaml
steps:
  - name: my-step
    uses: buz/<plugin>@<version>   # browse the catalog for ids and versions
    with:
      <input>: ${secrets.<NAME>}
```

## Repository manifests

Three generated files at the source root (`plugins/`) — plus one per-plugin
`meta.json` — each answers a different question:

| file | answers | refreshed |
|------|---------|-----------|
| [`plugins/index.json`](plugins/index.json) | **what exists** — signed `sequence` + `issued_at` header, then every plugin version with content sha256 and scalar meta | CI on green master; snapshot tags attach a copy |
| [`plugins/reviews.json`](plugins/reviews.json) | **what humans approved** — the review ledger (content hashes) | human review + CI badge refresh |
| [`plugins/revision.json`](plugins/revision.json) | **which catalog this is** — drift sentinel (digest over published versions + issue time); catalog-derived, so it cannot trail `HEAD` | derived from the index on every run |
| `plugins/buz/<id>/meta.json` | **what one plugin contains** — its versions, files, and hashes (fetched for a single-plugin refresh) | same run as the index |

All of them are generated **from the same tree, in one run** — index →
per-plugin `meta.json` → `revision.json` last, then the review ledger refresh
before signing. A source root may also carry `deprecations.json`: an overlay
that flags published versions as deprecated (carried into index/meta as
`deprecated`) without editing their immutable YAML or changing content hashes. Consistency is enforced, not assumed:

- `scripts/check_manifest_consistency.py` (run by the `validate` job) fails
  when a version in `index.json` has no review entry bound to the same
  `sha256`, when the ledger binds an older hash, or when an indexed version is
  missing from (or disagrees with) its plugin's `meta.json`. A missing badge
  is exactly what `require_reviewed` deployments reject; a stale `meta.json`
  is what a single-plugin refresh would serve.
- The index/meta drift gate regenerates and compares via `git status`, so a
  `meta.json` that was never committed (untracked) fails too — `git diff` alone
  would not see it.
- `.github/workflows/reconcile-manifests.yml` (daily) re-runs the same
  generation order and **opens a PR** when the committed manifests no longer
  match the specs.

> **The deployed site is the runtime truth.** CI refreshes the manifests on
> green `master` and writes them back with a bot commit, but that push is
> best-effort — the master ruleset blocks `GITHUB_TOKEN` pushes on personal
> accounts, and the `reconcile-manifests` PR is the permitted path. The site
> (`plugins.buz.schiplat.com/plugins/`) is therefore always current; the copies
> in git are the last reconciled snapshot. Air-gapped mirrors should take a
> catalog snapshot tag or the site's manifest set, and run
> `scripts/check_manifest_consistency.py` after each update — a plain
> `git clone` of `master` can lag behind the published catalog.

The index may also carry a detached signature (`index.json.sig`) so a Manager
can prove the index itself was not rewritten, mirrors included: generate it
with `buz-plugin keygen` (once) and `buz-plugin index --sign-key` (every
publish). **The private key is a CI secret and never lives in this
repository** — see [Plugin Tooling](https://buz.schiplat.com/docs/01-architecture/authoring/plugin-tooling/)
for the full procedure.

The same signing run produces `reviews.json.sig` when the ledger is present:
under a trust anchor a Manager refuses a review ledger it cannot verify, so
the badges cannot be forged by rewriting `reviews.json` alone. CI therefore
refreshes the ledger *before* signing, and the deploy write-back commits the
signature beside it.

The index header's `sequence` sits inside the signed bytes and only advances
when a plugin entry changes. A Manager that requires signatures remembers the
highest sequence it accepted and refuses a lower one, so an older catalogue
cannot be replayed; `issued_at` records when that catalogue version was
issued.

`revision.json` names the **catalog**, not a build: its value is a digest over
the published `(id, version, sha256)` triples (`scripts/gen_revision.py`), so
the same catalog always produces the same sentinel and the committed copy
cannot trail `HEAD`. It is written last, so a mirror that sees a new revision
knows the index beside it is complete. Mirrors compare two `revision.json`
files (from the deployed sites, not from git) to detect drift without pulling
the full index, and `scripts/check_manifest_consistency.py` fails when the
committed sentinel no longer matches the index. Never hand-edit hashes —
`scripts/gen_index.py` / `gen_revision.py` / `gen_reviews.py` (or the
`buz-plugin` CLI) generate them from the specs.
CI generates the manifests with `buz-plugin index`, derives the sentinel, and
immediately re-verifies the index with `--check` (`index.json` +
`index.json.sig` are published together). `scripts/gen_index.py` remains only
as a fallback for when the toolchain binary cannot be fetched.
See [governance](docs/governance.md) for the review process.

## Templates

The catalog — every plugin, version, engine, input, and a usage example — lives at **[plugins.buz.schiplat.com](https://plugins.buz.schiplat.com)** and is generated from the signed index, so it can never drift from what a Manager actually resolves. Each plugin directory also carries its own `README.md` with full details.

Missing a template you need? [Request a plugin](https://github.com/schiplat/buz-plugins/issues/new?template=plugin_request.yml) — open a wishlist issue and the maintainers/community will triage it; contributions under your own namespace are welcome.

Image-backed plugins require a Docker-enabled Runner and digest-pinned Linux `amd64` tool images; how those images are built, published, and pinned: [docs/plugin-images.md](docs/plugin-images.md), with authoring conventions in [docs/image-template-conventions.md](docs/image-template-conventions.md).

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

Step specs use `plugins/<namespace>/<name>/<version>.yaml` (for example `plugins/buz/<name>/<version>.yaml`). The namespace/name path follows the canonical step ID; multiple versions may coexist, and only YAML files are indexed. Every plugin directory must ship a non-empty `README.md` documenting the step's purpose, inputs, and a usage example — CI enforces this (`scripts/check_plugin_readmes.py`). Plugin names use a single technology noun (`docker`, `archive`, `setup-<lang>`) rather than verb phrases — the pipeline context supplies the verb. Governance and trust model — what the marketplace certifies, the official/community tiers, and the ssh engine policy: [docs/governance.md](docs/governance.md). Plugin-specific Docker build assets belong alongside that plugin in an `image/` subdirectory and are not scanned as templates. The canonical ID format is `<namespace>/<name>` (for example `buz/<name>`); optional `category` metadata is separate and never part of the ID. The `id` field is the canonical identity everywhere: use the complete ID in `uses:`, review commands, issues, and provenance. `@version` belongs on pipeline `uses:` references, while issue/review identifiers should use the ID itself (the issue title includes `@version` where useful). Required fields: `id`, `version` (`X.Y.Z`), `engine`, `run`. Inputs support `type` (string/number/boolean/choice/list), `required`, `default`, `masking`, `pattern`, `options`. Optional fields: `name`, `category`, `description`, `description_zh`, `author`, `author_url`, `source_repo`, `keywords`, `publisher` (`official` | `community`), `license`, `default_timeout`.

Community templates must declare `author` and `source_repo` — attribution is part of inclusion.

`source_repo` is the canonical HTTPS URL for the template's source, preferably a direct URL to the exact template file in its source repository. Use a commit-pinned URL when an immutable reference is needed. Official templates must also set it so the marketplace can link users from both the detail dialog and the crawlable static detail page. Avoid pointing only to a generic project homepage when a direct file URL is available. The site build checks that every official template has a valid HTTPS `source_repo` and that each generated detail page renders the matching link.

For community templates, `author_url` should link to the author's profile or organization page; `source_repo` should link to the actual source file/repository. Keep these attribution fields in sync when moving or renaming a source file.

Validate locally with the same checker CI uses:

```bash
buz-manager plugin-validate plugins/        # or a single file
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

- **validate**: downloads the `buz-manager` binary from the private buz release (no Rust toolchain, no source build) and runs `buz-plugin validate` on the recursively discovered YAML file list on every push/PR; also runs `shellcheck` over `scripts/*.sh`. `BUZ_REPO_PAT_V2` must be configured with read access to `schiplatv2/buz`; if absent, validation fails explicitly. GitHub does not expose repository secrets to fork PRs, so fork contributors need a maintainer-run validation or a branch within the repository before merge; required checks must not be treated as passing when validation is skipped.

  Optional version pin — repo Settings → Secrets and variables → Actions → **Variables** tab:

  | Variable | Value |
  |----------|-------|
  | `BUZ_VERSION` | Pin to the `v1.8.1` release (required by the 1.1.0 templates) or newer. Empty → latest release; do not merge/publish the 1.1.0 wave until Buz 1.8.1 is released. |
- **site**: builds the static browse site in an unprivileged read-only job and uploads it as an artifact. A separate publish job only runs on trusted pushes to `master`, then deploys to Cloudflare Pages if credentials are configured and persists the refreshed official review manifest.

  One-time deploy setup (repo Settings → Secrets and variables → Actions):

  | Secret | Value |
  |--------|-------|
  | `CLOUDFLARE_API_TOKEN` | CF API token with **Cloudflare Pages: Edit** permission |
  | `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account id |

  The first deploy creates the Pages project `buz-plugins`; then bind the custom domain **plugins.buz.schiplat.com** in CF Pages → project → Custom domains.
- **index**: on catalog snapshot tags (e.g. `2026.10.20`), regenerates `index.json` (id / version / sha256 per template) and attaches it to the GitHub release.

## Review badges

Every entry in `reviews.json` binds a review to a **content sha256** — any content change invalidates the badge automatically, so a reviewed v1.0 never launders trust for an unreviewed v1.1. The two namespaces carry different trust models:

- **Official (`buz/*`) — human first review, CI tracking after.** A brand-new official template is never auto-blessed: once a maintainer reviews the exact file contents, the id is recorded with the same manual command community templates use (`scripts/gen_reviews.py --date <d> --commit <sha> buz/<name>`; both scripts read `plugins/buz/index.json`, so run `scripts/gen_index.py` first whenever the local copy is missing or stale — it is a gitignored build product). From then on CI keeps every version of that id fresh on green master — `buz-plugin validate` + `lint_runs` + the egress allowlist must pass for the exact content hash, and the allowlist itself is part of review, not a build fix. CI regenerates ci-source entries on every push to `master` (`scripts/gen_reviews.py --auto`) and commits the refreshed manifest.
- **Community (`<author>/…`) — human-issued.** CI green is a prerequisite, never a substitute: a maintainer reviews the PR on GitHub, then records the entry using the canonical full ID from the YAML/index, e.g. `scripts/gen_reviews.py --date <d> --commit <sha> buz/<name>`. Manual invocation upserts the selected current content review and preserves unrelated review records.

Managers can enforce it:

```toml
[step_index]
reviewed_manifest = "/etc/buz/reviews.json"  # hash → "officially reviewed"
# require_reviewed = true                     # strict: reject unreviewed templates
```

Unreviewed templates resolve with a warning by default; the review status is recorded with each resolution's provenance. The badge means "static lint + manual review at this hash" — not a runtime-safety guarantee.

## Reporting problems

- **Broken / incorrect template** → [open an issue](https://github.com/schiplat/buz-plugins/issues/new?template=report.yml) with the canonical full step ID (including `buz/` for official steps) and version, e.g. `buz/<name>@<version>`
- **Suspected backdoor / malicious behavior** → **do not post details publicly**: use [Private vulnerability reporting](https://github.com/schiplat/buz-plugins/security/advisories/new). Maintainers triage privately, respond within **7 days**, and publish an outcome after handling.

Triage outcomes: benign → closed; violating → template **removed from the index** (takedown) and, when applicable, a note published; fixable → author PR with a version bump (content hash changes, so the review badge auto-invalidates until re-reviewed).

## Namespace note

In Phase 1 (local index) a `uses:` reference is the complete template `id` plus `@version` — e.g. `buz/<name>@<version>`. The index `file` value is a repository-relative POSIX path (for example `plugins/buz/<name>/<version>.yaml`); consumers should resolve it relative to the index/repository root, never depend on an absolute build-machine path. Namespace→index-source bindings (`community/...` pointing at a configured remote index) arrive with Phase 2 `https` indexes.

## License

Apache-2.0 — see [LICENSE](LICENSE).
