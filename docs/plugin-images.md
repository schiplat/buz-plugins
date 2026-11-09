# Plugin tool images

Authoring conventions for templates that ship a tool image (image reference
lifecycle, registering a family, run-block rules): see
[image-template-conventions.md](image-template-conventions.md).

Images target Linux `amd64` (x86_64) only. A push to `master` automatically triggers builds when an image build context changes — the OSS/S3 upload families under `plugins/buz/oss-upload` and `plugins/buz/s3-upload`, or the language toolchain families under `plugins/buz/setup-rust`, `plugins/buz/setup-ruby`, `plugins/buz/setup-php`, `plugins/buz/setup-lua`, `plugins/buz/setup-python`, `plugins/buz/setup-node`, `plugins/buz/setup-java`, and `plugins/buz/setup-go`. Template YAML edits do not rebuild an image (its digest does not depend on the spec text). The workflow builds only the corresponding image family; if multiple plugin families change in one push, it builds each as a separate matrix job. Documentation, workflow files, nested directories, and unrelated paths do not trigger a build. Automatic image tags use `X.Y.Z-build.<run number>.<run attempt>`, making each run unique. The workflow is push-triggered only; it has no manual dispatch entry point. Configure `DOCKERHUB_USERNAME` as a repository Actions variable and `DOCKERHUB_TOKEN` as a repository Actions secret. The workflow refuses an existing version tag and writes a successful build's digest to the run summary.

## Versioning contract

**镜像版本 ≠ 模板版本;digest 才是锁。** The rules that make this safe:

- Each image family has exactly **one** rolling build tag sequence
  (`X.Y.Z-build.<run>.<attempt>`) plus a set of **immutable manifest
  digests**. Template specs never reference a mutable tag: every published
  spec pins `image@sha256:<64 hex>`, and pulling by digest yields byte-for-byte
  the reviewed build.
- **A template version is the immutable pair** (call contract + pinned
  digest). Editing `image/Dockerfile` never retroactively changes what an
  already-published template version runs — the pin flow refuses to replace an
  existing digest and creates a new patch version instead (`1.0.2` stays on
  its digest; the new build lands in `1.0.3`).
- **`image/` describes the next build only.** The tree holds one Dockerfile
  per family; the recipe behind a historical digest lives in git history. The
  mapping is recorded in each family's build ledger,
  `<plugin>/image/BUILDS.md`, appended automatically by the pin workflow on
  every pin event:

  ```
  | digest | pinned into | Dockerfile commit | workflow run | date |
  ```

  Read it as the authoritative answer to "which template version runs which
  image, and where was that image's recipe built".
- **Pre-pin window**: the initial `1.0.0` spec is updated *in place* while it
  still references the placeholder `:1.0.0` tag (before its first digest pin).
  During that window the same `@1.0.0` resolves to different images over
  time — this is the intended unpublished state; complete the first pin
  promptly after registering a family.

## Build → pin flow

After each successful matrix build, the workflow uploads that family's manifest digest and opens or updates a family-specific PR pinning its template to `image@sha256:...` and appending the event to the family's `image/BUILDS.md` ledger. If both families are selected and one build fails, the successful family can still open its PR; fix the failed build before retrying it. Identical digests do not create empty PRs. The PR branch is `automation/pin-<family>`.

The PR job uses `GITHUB_TOKEN` by default and requires `contents: write` and `pull-requests: write` repository workflow permissions. To make the generated PR trigger the full CI workflow, configure an Actions secret named `BUZ_PLUGIN_GITHUB_PR_TOKEN` with a fine-grained PAT or GitHub App token that can read and write repository contents and pull requests. Without this token, GitHub suppresses most new workflow runs created with `GITHUB_TOKEN`; the PR is still created, but checks may require a maintainer-triggered run. Keep the token narrowly scoped and rotate it according to its expiration policy.

Auto-merge is currently paused while the repository is private and its branch protection requirements are being verified. The workflow creates or updates the digest PR but does not enable or perform auto-merge; a maintainer must review and merge it manually. Once the repository can enforce required CI checks, auto-merge can be re-enabled.

The run-ID version tag identifies the build, while templates use immutable manifest digests. The initial `1.0.0` template is only updated in place when pinning the first image release from its `:1.0.0` tag. Later template versions are immutable: if a build produces a new digest after the `1.0.2` trigger template exists, the digest PR creates `1.0.3` rather than rewriting `1.0.2`; identical digests do not create an empty PR. A version tag by itself is not an immutable production pin. The `[skip image build]` marker on generated pin PR titles and commits prevents the PR merge from triggering another image build; if a push combines a pin commit with other commits, non-pin commits are still inspected for changed plugin paths.

Removing an old template file does not remove or change its Docker image; the digest stays pullable for every pipeline still pinned to that version.

## Base-image digest pinning

Every Dockerfile `FROM` line carries the manifest-list digest its tag
resolved to at pin time (`FROM golang:1.26-bookworm@sha256:…`), so rebuilding
the same recipe is deterministic until a base is deliberately refreshed. The
**`pin-base-images`** workflow (manual dispatch) re-resolves every base via
the registry manifest API and opens one PR refreshing whatever moved
upstream — the tag stays readable, only the digest updates. Merging that PR
changes every family's build inputs: the publish workflow rebuilds all
families and the usual per-family digest-pin PRs follow.

## Future hardening

- **Multi-arch**: images are `linux/amd64`-only. Apple Silicon / arm64 hosts
  need `linux/arm64` legs (buildx manifest list); because a manifest-list
  digest differs from the single-arch digest, this is a coordinated
  pin bump across all families. Cross-building toolchain images needs native
  arm64 runners or QEMU emulation (slow for `RUN`-heavy recipes); plan the
  runner budget before switching it on.

## Runtime requirements and credentials

Docker templates require Docker to be enabled in the Manager/Runner policy and the Runner host to have the Docker CLI and daemon available. The invocation contract (`sh -elc`, workspace mounted at `/buz/workspace`) is defined by the buz [Plugin Contract](https://github.com/schiplat/buz/blob/master/docs/content/docs/01-architecture/authoring/plugin-contract.md); these images therefore set `CMD ["sh"]` and do not define a command-consuming `ENTRYPOINT`.

OSS upload requires an HTTPS endpoint and region. The entrypoint passes credentials through ossutil v2's documented `OSS_ACCESS_KEY_ID`, `OSS_ACCESS_KEY_SECRET`, `OSS_ENDPOINT`, `OSS_REGION`, and optional `OSS_SESSION_TOKEN` environment variables. S3 upload requires an HTTPS endpoint and region, uses masked AWS credentials, and supports optional STS session tokens. Use least-privilege credentials and short-lived tokens where possible. Runner egress policy must allow the requested storage endpoint. The shell egress checker records endpoint inputs but cannot inspect network calls made inside an image, so image behavior and destination restrictions require separate review.

Use `source` paths relative to the workspace. Both image-side scripts resolve the path and reject files whose resolved paths escape the mounted workspace. Each upload replaces the destination object at the supplied key, so choose the key and rerun behavior intentionally.

## Template layout

Step specs use `plugins/<namespace>/<name>/<version>.yaml`, such as `plugins/buz/feishu/1.0.0.yaml`. The namespace/name path follows the canonical step ID, versions may coexist, and `category` remains display/filter metadata rather than identity or directory structure.
