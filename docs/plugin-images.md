# Plugin tool images

The official upload steps use two plugin-specific Docker images built for Linux `amd64` (x86_64):

- `plugins/buz/oss-upload/image/` builds `schiplat/buz-plugins-oss-tools` with Aliyun ossutil v2.
- `plugins/buz/s3-upload/image/` builds `schiplat/buz-plugins-aws-tools` with the official AWS CLI v2.

Each image context lives beside its plugin's versioned YAML spec. Catalog tools recursively index only `.yaml` and `.yml` files, so Dockerfiles, the AWS signing key, and shell helpers are not mistaken for step templates. The shell-only plugins do not need image contexts.

## Build and publish

Images target Linux `amd64` (x86_64) only. Publishing is manual: maintainers dispatch `.github/workflows/publish-plugin-image.yml` from `master`, select an allowlisted image family, and enter a new `X.Y.Z` image tag. Configure `DOCKERHUB_USERNAME` as a repository Actions variable and `DOCKERHUB_TOKEN` as a repository Actions secret before dispatch. The workflow refuses an already existing version tag and writes the published image digest to the run summary.

The workflow never runs on ordinary pushes or tags. Use a new image version for each changed image. After publishing, update the matching template's `image` to the actual manifest digest, such as `docker.io/schiplat/buz-plugins-aws-tools@sha256:<digest>`, and revalidate/re-review that spec hash. A version tag is not an immutable production pin.

The upload specs currently reference planned `1.0.0` tags. The images have not been published. These specs are not production-ready until the images are published and their references are changed to verified manifest digests.

## Runtime requirements and credentials

Docker templates require Docker to be enabled in the Manager/Runner policy and the Runner host to have the Docker CLI and daemon available. Buz invokes the image command through `sh -elc` and mounts the workspace at `/buz/workspace`; these images therefore set `CMD ["sh"]` and do not define a command-consuming `ENTRYPOINT`.

OSS upload requires an HTTPS endpoint and region. The entrypoint passes credentials through ossutil v2's documented `OSS_ACCESS_KEY_ID`, `OSS_ACCESS_KEY_SECRET`, `OSS_ENDPOINT`, `OSS_REGION`, and optional `OSS_SESSION_TOKEN` environment variables. S3 upload requires an HTTPS endpoint and region, uses masked AWS credentials, and supports optional STS session tokens. Use least-privilege credentials and short-lived tokens where possible. Runner egress policy must allow the requested storage endpoint. The shell egress checker records endpoint inputs but cannot inspect network calls made inside an image, so image behavior and destination restrictions require separate review.

Use `source` paths relative to the workspace. Both image-side scripts resolve the path and reject files whose resolved paths escape the mounted workspace. Each upload replaces the destination object at the supplied key, so choose the key and rerun behavior intentionally.

## Template layout

Step specs use `plugins/<namespace>/<name>/<version>.yaml`, such as `plugins/buz/feishu/1.0.0.yaml`. The namespace/name path follows the canonical step ID, versions may coexist, and `category` remains display/filter metadata rather than identity or directory structure.
