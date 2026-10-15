# Image template conventions

Conventions a step template must follow to participate in the automatic
tool-image build pipeline. Mechanics of the build/publish workflow itself live
in [plugin-images.md](plugin-images.md); this page is the authoring contract.

## Two template kinds

| Kind | Examples | Shape |
|------|----------|-------|
| **Helper** | `buz/oss-upload`, `buz/s3-upload` | The image installs a fixed helper (`entrypoint.sh` → `/usr/local/bin/<helper>`); the spec's `run:` is exactly `exec /usr/local/bin/<helper>` |
| **Toolchain** | `buz/setup-rust` … `buz/setup-go` (rust, ruby, php, lua, python, node, java, go) | The image ships language toolchains; the spec selects one via `version` and executes a required `script` input |

## Directory layout and identity

```text
plugins/<namespace>/<name>/
├── README.md           # required — repo rule, enforced by check_plugin_readmes.py in CI
├── 1.0.0.yaml          # one file per template version, X.Y.Z == `version:` field
├── 1.0.1.yaml          # later versions are added, never rewritten (see lifecycle)
└── image/
    ├── Dockerfile      # linux/amd64 only — no TARGETARCH/arm64/aarch64 anywhere
    └── entrypoint.sh   # helper kind only
```

- Canonical ID: lowercase `<namespace>/<name>`, exactly two segments (e.g.
  `buz/setup-rust`). The ID is the identity everywhere; `category` is display
  metadata only.
- Spec `version:` must be `X.Y.Z` and must match the filename stem.
- Required top-level fields: `id`, `version`, `engine` (`docker` for image
  families), `run`. Optional: `name`, `category`, `description`,
  `description_zh`, `author`, `source_repo`, `keywords`, `publisher`,
  `license`, `default_timeout`.
- **Input fields accept only**: `type`, `required`, `default`, `options`,
  `pattern`, `masking`, `description` — there is no `description_zh` on
  inputs. Input `type` is one of `string`, `number`, `boolean`, `choice`
  (with `options`), `list`.
- The Manager validates specs with `buz-manager step-validate`; anything
  outside the schema above fails CI.

## Image reference lifecycle

The `image:` field is the contract between a template and the build pipeline:

1. **Initial template** must reference `docker.io/schiplat/<family-image>:1.0.0`
   (the literal tag, matching the spec version `1.0.0`). The tag does not need
   to exist in the registry yet.
2. A push that touches `image/**` (or the template) publishes
   `<image>:<VERSION>-build.<RUN_NUMBER>.<RUN_ATTEMPT>` — a unique build tag,
   never a production pin.
3. The `pin-template` job then opens/updates a PR on branch
   `automation/pin-<family>` titled `[skip image build] Pin … image digest`
   that rewrites the `image:` line to `@sha256:<manifest digest>`.
4. The very first pin updates the `1.0.0` template **in place** (only allowed
   while it still references `:1.0.0`). Every later digest creates a new
   patch-version file (`1.0.1.yaml`, …) and never rewrites a published
   version; replacing a non-initial tag reference is refused.

Rules that keep this machine-checkable: a build tag by itself is not an
immutable pin; production references must be `@sha256:`-pinned; pin PRs stay
manual-merge (no auto-merge in CI); commits and titles carry
`[skip image build]` so pin merges do not re-trigger builds.

## Registering a new image family

All touchpoints must agree — `scripts/check_plugin_images.py` fails CI when
they diverge:

1. `plugins/<ns>/<name>/image/Dockerfile` (helper kind adds `entrypoint.sh`).
2. `plugins/<ns>/<name>/<X.Y.Z>.yaml` with `image: …:<X.Y.Z-tag>` as above.
3. `plugins/<ns>/<name>/README.md` — required for every plugin; CI fails a
   directory that ships templates without one.
3. `scripts/select_plugin_image_families.py` → `FAMILY_PATHS`.
4. `scripts/pin_plugin_image.py` → `FAMILIES` (step id, image, plugin dir).
5. `.github/workflows/publish-plugin-image.yml` → push `paths` list, the
   `Validate push and resolve image context` case, the pin-job `plugin_dir`
   case, and the pin-PR `title` case.
6. `scripts/check_plugin_images.py` → `EXPECTED` (helper) or `TOOLCHAIN`
   (toolchain) entry.
7. `egress-allowlist.json` → an entry for the new ID (see below).
8. `tests/test_scripts.py` → the workflow `paths` set assertion.
9. `README.md` template table (and `docs/plugin-images.md` family list when
   the prose names families).

## run-block rules

The authoritative runtime-side contract — workspace layout, `sh -elc`
invocation, `INPUT_*` passing, `BUZ_*` metadata environment, secret masking,
and the `requires_buz` version gate — is the
[Plugin Contract](https://github.com/schiplat/buz/blob/master/docs/content/docs/01-architecture/authoring/plugin-contract.md)
in the buz documentation; this section only lists the authoring rules that
follow from it.

Buz executes a Docker step's `run:` block via `sh -elc` inside the image with
the workspace mounted at `/buz/workspace` and `with:` values exposed as
`INPUT_*` environment variables. Images therefore set `CMD ["sh"]` and no
command-consuming `ENTRYPOINT` (helper images wrap their logic in the
installed entrypoint script instead).

- POSIX sh only (the runtime image is Debian; `sh` is dash).
- `scripts/lint_runs.py` rejects, among others: `eval`, piping into
  `sh`/`bash`/`python`, `curl … | sh`, `base64 -d`, `/dev/tcp/`, `nc … -e`,
  plaintext `http://` downloads, `history -c`, `chmod +x` immediately
  followed by execution. Execute dynamic input by writing it to a temp file
  and running `sh -e <file>` (see the `buz/setup-*` templates).
- Validate any path-like input against workspace escapes before use:
  reject `/*`, `..`, `../*`, `*/../*`, `*/..`, then `cd /buz/workspace` and
  resolve/verify (pattern used by `oss-upload` and the setup templates).
- Toolchain templates must declare a required `script` input and reference
  `INPUT_SCRIPT` in `run:` (enforced by `check_plugin_images.py`).
- Network-touching inputs (`url`, `webhook`, `endpoint`, …) must be declared
  in `egress-allowlist.json` under `endpoint_inputs` for the template ID; the
  check is an exact match, and literal hosts in `run:` may only be a subset
  of the entry's `hosts`. Every official `buz/*` template needs an entry even
  if empty.
- Images making their own network calls (toolchain downloads, package
  registries) are outside the shell egress checker's view — image behavior
  and Runner egress policy need separate review (documented in
  [plugin-images.md](plugin-images.md)).

## Version aliases

Every toolchain template's `version` input accepts three channel aliases
alongside concrete versions. They resolve to toolchains shipped in (or
installed by) the image; rebuilding the image with newer lines is what moves
an alias forward — a template pin never changes an already-saved pipeline.

| Alias | Meaning |
|-------|---------|
| `stable` | The recommended default line (also the template default) |
| `lts` | The longest-support line; where the language has no LTS concept, equals `stable` |
| `dev` | The newest line: a real dev channel where the ecosystem provides one (rust → rustup nightly, go → gotip build, node → current line), otherwise the newest shipped line |

Concrete versions always remain available and are the only way to select an
older line. Each template's `version` description states its exact alias
mapping; keep it in sync when the image gains lines.

## Buz compatibility

CI validates specs with a pinned `BUZ_VERSION` (repository variable), so a
Buz release that changes the spec schema or the Plugin Contract surfaces as
a failing plugins build instead of a runtime break. After a Buz release,
bump `BUZ_VERSION` and let CI confirm compatibility before saving pipelines
that use new schema features.

## Pre-push validation checklist

Never push a HEAD commit whose message contains `[skip ci]` (or the other
GitHub skip markers): it suppresses **every** push-triggered workflow for
that push — the site deploy and the image builds included. The marker is
reserved for commits CI itself creates after a completed run (review-badge
refreshes, digest pins). If you refresh `reviews.json` locally, use a
different commit message.

```bash
python3 tests/test_scripts.py                          # script + wiring tests
python3 scripts/lint_runs.py plugins                   # run-block heuristics
python3 scripts/egress.py --print --expect egress-allowlist.json
python3 scripts/check_plugin_images.py                 # workflow structure gate
python3 scripts/gen_index.py --output /tmp/index.json  # index dry run
buz-manager step-validate $(find plugins -name '*.y?ml' -not -path '*/.*')
sh -n <extracted run block>                            # optional: syntax check
```

All of these run in CI as well; the image build itself only happens on
`master` pushes, where a wrong FROM tag, download URL, or checksum fails the
build visibly.
