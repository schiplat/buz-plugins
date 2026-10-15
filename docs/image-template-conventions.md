# Image template conventions

Conventions a step template must follow to participate in the automatic
tool-image build pipeline. Mechanics of the build/publish workflow itself live
in [plugin-images.md](plugin-images.md); this page is the authoring contract.

## Two template kinds

| Kind | Examples | Shape |
|------|----------|-------|
| **Helper** | `buz/oss-upload`, `buz/s3-upload` | The image installs a fixed helper (`entrypoint.sh` → `/usr/local/bin/<helper>`); the spec's `run:` is exactly `exec /usr/local/bin/<helper>` |
| **Toolchain** | `buz/setup-rust`, `buz/setup-ruby`, `buz/setup-php`, `buz/setup-lua` | The image ships language toolchains; the spec selects one via `version` and executes a required `script` input |

## Directory layout and identity

```text
plugins/<namespace>/<name>/
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

## Pre-push validation checklist

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
