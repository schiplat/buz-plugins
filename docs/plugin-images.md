# Plugin tool images

The official upload steps use two plugin-specific Docker images built for Linux `amd64` (x86_64):

- `plugins/buz/oss-upload/image/` builds `schiplat/buz-plugins-oss-tools` with Aliyun ossutil v2.
- `plugins/buz/s3-upload/image/` builds `schiplat/buz-plugins-aws-tools` with the official AWS CLI v2.

Each image context lives beside its plugin's versioned YAML spec. Catalog tools recursively index only `.yaml` and `.yml` files, so Dockerfiles, the AWS signing key, and shell helpers are not mistaken for step templates. The shell-only plugins do not need image contexts.

## Build and publish

Images target Linux `amd64` (x86_64) only. On pushes to `master`, changes under `plugins/buz/oss-upload/image/` automatically publish only the OSS image, and changes under `plugins/buz/s3-upload/image/` publish only the AWS CLI image. If both contexts change in one push, both images are built as separate matrix jobs. Automatic tags use `1.0.<GitHub Actions run ID>` so each workflow run gets a unique tag. Changes to templates, docs, workflow files, or other paths do not trigger image builds.

Maintainers can also dispatch `.github/workflows/publish-plugin-image.yml` manually from `master`, select one allowlisted image family, and enter a new `X.Y.Z` image tag. Configure `DOCKERHUB_USERNAME` as a repository Actions variable and `DOCKERHUB_TOKEN` as a repository Actions secret. The workflow refuses an already existing version tag and writes the published image digest to the run summary.

After each successful matrix build, the workflow uploads that family’s manifest digest and opens or updates a family-specific PR pinning its template to `image@sha256:...`. If both families are selected and one build fails, the successful family can still open its PR; fix the failed build before retrying it. The first image release automatically pins the planned `1.0.0` template; later digest changes create a new patch template version and leave published versions unchanged. Identical digests do not create empty PRs. The PR branch is `automation/pin-<family>`.

The PR job uses `GITHUB_TOKEN` by default and requires `contents: write` and `pull-requests: write` repository workflow permissions. To make the generated PR trigger the full CI workflow, configure an Actions secret named `BUZ_PLUGIN_GITHUB_PR_TOKEN` with a fine-grained PAT or GitHub App token that can read and write repository contents and pull requests. Without this token, GitHub suppresses most new workflow runs created with `GITHUB_TOKEN`; the PR is still created, but checks may require a maintainer-triggered run. Keep the token narrowly scoped and rotate it according to its expiration policy.

After opening or updating the PR, the workflow enables GitHub auto-merge. In repository settings, enable **Allow auto-merge** and protect `master` with the required checks that must pass before merging (at minimum, the `ci / validate` and `ci / site` checks; use the exact check names GitHub reports). GitHub waits for required checks and any other branch protection or ruleset requirements before merging; auto-merge does not bypass them. If checks are not marked required, GitHub may not wait for them. The merge can also remain queued if an approval or merge-queue requirement is unmet. Auto-merge is enabled only for this trusted `master` workflow run.

Automatic builds run only for changes under the two image contexts on `master`; template, docs, workflow, and unrelated pushes do not trigger an image build. The run-ID version tag identifies a build, while the template uses its immutable digest. The `1.0.0` spec is only updated in place for the initial pin from the planned `:1.0.0` tag; later published template versions are immutable. A version tag by itself is not an immutable production pin.

The upload specs currently reference planned `1.0.0` tags until a successful build’s digest PR is merged. They are not production-ready until their references use verified manifest digests.

## Runtime requirements and credentials

Docker templates require Docker to be enabled in the Manager/Runner policy and the Runner host to have the Docker CLI and daemon available. Buz invokes the image command through `sh -elc` and mounts the workspace at `/buz/workspace`; these images therefore set `CMD ["sh"]` and do not define a command-consuming `ENTRYPOINT`.

OSS upload requires an HTTPS endpoint and region. The entrypoint passes credentials through ossutil v2's documented `OSS_ACCESS_KEY_ID`, `OSS_ACCESS_KEY_SECRET`, `OSS_ENDPOINT`, `OSS_REGION`, and optional `OSS_SESSION_TOKEN` environment variables. S3 upload requires an HTTPS endpoint and region, uses masked AWS credentials, and supports optional STS session tokens. Use least-privilege credentials and short-lived tokens where possible. Runner egress policy must allow the requested storage endpoint. The shell egress checker records endpoint inputs but cannot inspect network calls made inside an image, so image behavior and destination restrictions require separate review.

Use `source` paths relative to the workspace. Both image-side scripts resolve the path and reject files whose resolved paths escape the mounted workspace. Each upload replaces the destination object at the supplied key, so choose the key and rerun behavior intentionally.

## Template layout

Step specs use `plugins/<namespace>/<name>/<version>.yaml`, such as `plugins/buz/feishu/1.0.0.yaml`. The namespace/name path follows the canonical step ID, versions may coexist, and `category` remains display/filter metadata rather than identity or directory structure.
