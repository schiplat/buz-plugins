#!/usr/bin/env python3
"""Validate plugin tool-image release wiring without building or publishing images."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/publish-plugin-image.yml"
EXPECTED = {
    "oss-tools": (
        "docker.io/schiplat/buz-plugins-oss-tools",
        "plugins/buz/oss-upload/image",
        "plugins/buz/oss-upload/1.0.0.yaml",
    ),
    "aws-tools": (
        "docker.io/schiplat/buz-plugins-aws-tools",
        "plugins/buz/s3-upload/image",
        "plugins/buz/s3-upload/1.0.0.yaml",
    ),
}


def image_reference_matches(image: str, reference: object) -> bool:
    if not isinstance(reference, str):
        return False
    return reference == f"{image}:1.0.0" or re.fullmatch(
        re.escape(image) + r"@sha256:[0-9a-f]{64}", reference
    ) is not None


def main() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = workflow.get("on") or workflow.get(True) or {}
    if not {"workflow_dispatch", "push"} == set(triggers):
        raise SystemExit("image publishing must support workflow_dispatch and path-filtered push")
    push = triggers["push"]
    if push.get("branches") != ["master"] or set(push.get("paths", [])) != {
        "plugins/buz/oss-upload/image/**",
        "plugins/buz/s3-upload/image/**",
    }:
        raise SystemExit("automatic publishing must be limited to image contexts on master")

    dispatch_inputs = triggers["workflow_dispatch"].get("inputs", {})
    family = dispatch_inputs.get("image_family", {})
    if family.get("type") != "choice" or set(family.get("options", [])) != set(EXPECTED):
        raise SystemExit("image_family must be limited to the allowlisted families")
    version = dispatch_inputs.get("version", {})
    if version.get("required") is not True:
        raise SystemExit("image version must be required")

    detect_job = workflow.get("jobs", {}).get("detect", {})
    detect_outputs = detect_job.get("outputs", {})
    if detect_outputs.get("families") != "${{ steps.select.outputs.families }}":
        raise SystemExit("family selection job must expose detected image families")
    detect_steps = detect_job.get("steps", [])
    select_step = next(
        (step for step in detect_steps if isinstance(step, dict) and step.get("id") == "select"),
        None,
    )
    select_run = select_step.get("run", "") if select_step else ""
    for family, context in (
        ("oss-tools", "plugins/buz/oss-upload/image/*"),
        ("aws-tools", "plugins/buz/s3-upload/image/*"),
    ):
        if context not in select_run or f"families+=({family})" not in select_run:
            raise SystemExit(f"changed image context must select only {family}")
    if "GITHUB_RUN_ID" not in select_run or "git diff --name-only" not in select_run:
        raise SystemExit("push builds must use unique run-ID tags and detect changed paths")
    if "git diff-tree --root --no-commit-id --name-only -r" not in select_run:
        raise SystemExit("initial push builds must also select only changed image contexts")
    if "families+=(oss-tools aws-tools)" in select_run:
        raise SystemExit("push builds must not rebuild unchanged image families")

    publish_job = workflow.get("jobs", {}).get("publish", {})
    if publish_job.get("needs") != "detect":
        raise SystemExit("image publishing must depend on family detection")
    strategy = publish_job.get("strategy", {}).get("matrix", {})
    if strategy.get("image_family") != "${{ fromJSON(needs.detect.outputs.families) }}":
        raise SystemExit("publish matrix must contain only detected image families")
    steps = publish_job.get("steps", [])
    runner_publishers = [
        step for step in steps
        if isinstance(step, dict) and step.get("uses", "").startswith("docker/build-push-action@")
    ]
    if not runner_publishers[0].get("uses", "").endswith(
        "@1ca370b3a9802c92e886402e0dd88098a2533b12"
    ):
        raise SystemExit("build-push action must be pinned to the verified v6.4.1 commit")
    with_config = runner_publishers[0].get("with", {})
    if with_config.get("push") is not True or with_config.get("platforms") != "linux/amd64":
        raise SystemExit("release action must push only the Linux amd64 image")
    if with_config.get("context") != "${{ steps.image.outputs.context }}":
        raise SystemExit("build context must come from the validated family selector")
    if with_config.get("tags") != "${{ steps.image.outputs.tag }}":
        raise SystemExit("published tag must come from the validated family and version")
    if not any(
        isinstance(step, dict)
        and step.get("name") == "Reject an existing image version tag"
        and "docker buildx imagetools inspect \"$IMAGE:$VERSION\"" in step.get("run", "")
        and "Could not determine whether image tag exists; refusing to publish." in step.get("run", "")
        and "status code: 404" in step.get("run", "")
        for step in steps
    ):
        raise SystemExit("workflow must refuse existing tags and fail closed on registry errors")
    for action in ("docker/setup-buildx-action@", "docker/login-action@"):
        if not any(isinstance(step, dict) and step.get("uses", "").startswith(action) for step in steps):
            raise SystemExit(f"missing required image publishing action: {action}")
    if any(
        isinstance(step, dict) and step.get("uses", "").startswith("docker/setup-qemu-action@")
        for step in steps
    ):
        raise SystemExit("QEMU is unnecessary for the single-platform amd64 image")

    text = WORKFLOW.read_text(encoding="utf-8")
    validate_step = next(
        step for step in steps
        if isinstance(step, dict) and step.get("name") == "Validate dispatch and resolve image context"
    )
    validate_run = validate_step.get("run", "")
    shell_lines = "\n".join(
        line for line in validate_run.splitlines()
        if not line.lstrip().startswith("#")
    )
    family_matches = re.findall(r'^\s*([a-z][a-z0-9-]*)\)\s*$', shell_lines, re.MULTILINE)
    if set(family_matches) != set(EXPECTED):
        raise SystemExit("shell family selector must match the allowlisted families")
    if '[[ ! "$IMAGE_VERSION" =~ ^[0-9]+\\.[0-9]+\\.[0-9]+$ ]]' not in shell_lines:
        raise SystemExit("workflow must reject versions outside X.Y.Z")
    if '"$GITHUB_REF" != "refs/heads/master"' not in shell_lines:
        raise SystemExit("publishing must be restricted to master")
    if "docker/login-action@" not in text:
        raise SystemExit("workflow must authenticate to Docker Hub")
    if not re.search(r"\$\{\{\s*vars\.DOCKERHUB_USERNAME\s*\}\}", text) or not re.search(
        r"\$\{\{\s*secrets\.DOCKERHUB_TOKEN\s*\}\}", text
    ):
        raise SystemExit("Docker Hub username must come from a repository variable and token from a secret")
    if "steps.build.outputs.digest" not in text:
        raise SystemExit("workflow must record the build manifest digest")

    pin_job = workflow.get("jobs", {}).get("pin-template", {})
    if pin_job.get("needs") != ["detect", "publish"]:
        raise SystemExit("digest pin job must wait for detection and publishing")
    if "github.ref == 'refs/heads/master'" not in pin_job.get("if", ""):
        raise SystemExit("digest pin job must run only from the trusted master branch")
    if "always()" not in pin_job.get("if", "") or "needs.publish.result != 'cancelled'" not in pin_job.get("if", "") or "needs.detect.result == 'success'" not in pin_job.get("if", ""):
        raise SystemExit("digest pin job must run for selected builds, even if a publish matrix leg fails")
    if pin_job.get("permissions") != {"contents": "write", "pull-requests": "write"}:
        raise SystemExit("digest pin job must have only contents and pull-request write permissions")
    if pin_job.get("strategy", {}).get("matrix", {}).get("image_family") != "${{ fromJSON(needs.detect.outputs.families) }}":
        raise SystemExit("digest pin job must process only the selected image families")
    pin_steps = pin_job.get("steps", [])
    if not any(
        isinstance(step, dict)
        and step.get("uses", "").startswith("actions/download-artifact@")
        and step.get("with", {}).get("name") == "plugin-image-digest-${{ matrix.image_family }}"
        and step.get("continue-on-error") is True
        for step in pin_steps
    ):
        raise SystemExit("digest pin job must tolerate the artifact missing for a failed matrix build")
    if not any(
        isinstance(step, dict)
        and step.get("uses", "").startswith("actions/upload-artifact@")
        and "plugin-image-digest-${{ matrix.image_family }}" == step.get("with", {}).get("name")
        for step in steps
    ):
        raise SystemExit("each published image must upload its digest in a family-specific artifact")
    if not any(
        isinstance(step, dict)
        and step.get("name") == "Install pin script dependencies"
        and "pyyaml" in step.get("run", "")
        for step in pin_steps
    ):
        raise SystemExit("pin job must install the YAML parser required by the update script")
    if not any(
        isinstance(step, dict)
        and step.get("name") == "Create or update digest pin pull request"
        and "git commit" in step.get("run", "")
        and "git push" in step.get("run", "")
        and "gh pr create" in step.get("run", "")
        and "gh pr edit" in step.get("run", "")
        and "gh pr merge" in step.get("run", "")
        and "--auto" in step.get("run", "")
        for step in pin_steps
    ):
        raise SystemExit("successful image builds must create or update a digest pin pull request")
    pin_script = (ROOT / "scripts/pin_plugin_image.py").read_text(encoding="utf-8")
    if "refusing to overwrite existing template version" not in pin_script or "target_version" not in pin_script:
        raise SystemExit("digest updates must preserve published template versions")
    if "automation/pin-${IMAGE_FAMILY}" not in text or "BUZ_PLUGIN_GITHUB_PR_TOKEN || github.token" not in text:
        raise SystemExit("digest PRs must use a stable family branch and the documented optional token")

    for slug, (image, context, spec_file) in EXPECTED.items():
        if f'docker.io/schiplat/{image.rsplit("/", 1)[-1]}' not in shell_lines:
            raise SystemExit(f"{slug}: image name is absent from validated family selector")
        if context not in shell_lines:
            raise SystemExit(f"{slug}: context is absent from validated family selector")
        dockerfile = (ROOT / context / "Dockerfile").read_text(encoding="utf-8")
        helper_name = "buz-oss-upload" if slug == "oss-tools" else "buz-s3-upload"
        if f"COPY entrypoint.sh /usr/local/bin/{helper_name}" not in dockerfile:
            raise SystemExit(f"{slug}: image must install its upload helper")
        if f"RUN chmod 0755 /usr/local/bin/{helper_name}" not in dockerfile:
            raise SystemExit(f"{slug}: upload helper must be executable")
        if "TARGETARCH" in dockerfile or "arm64" in dockerfile or "aarch64" in dockerfile:
            raise SystemExit(f"{slug}: Dockerfile must target Linux amd64 only")
        if slug == "oss-tools" and (
            "OSSUTIL_SHA256_AMD64" not in dockerfile
            or "ossutil-${OSSUTIL_VERSION}-linux-amd64/ossutil" not in dockerfile
        ):
            raise SystemExit("oss-tools: install the checksum-verified amd64 binary from its archive directory")
        if slug == "aws-tools" and (
            "awscli-exe-linux-x86_64-" not in dockerfile
            or "FB5DB77FD5C118B80511ADA8A6310ACC4672475C" not in dockerfile
            or "Y/RlOHXlzLuQMRE6sR1wOdRxc9TsrNWTGiBK65cvSWOy03JeBkQQ8pesqltiyxI9" not in (ROOT / context / "aws-cli-team-public-key.asc").read_text(encoding="utf-8")
        ):
            raise SystemExit("aws-tools: verify the x86_64 AWS CLI against the intact pinned public key")
        spec = yaml.safe_load((ROOT / spec_file).read_text(encoding="utf-8"))
        if spec.get("engine") != "docker" or not image_reference_matches(image, spec.get("image")):
            raise SystemExit(f"{slug}: template image reference must use the expected tag or a pinned sha256 digest")
        if spec.get("run", "").strip() != f"exec /usr/local/bin/{helper_name}":
            raise SystemExit(f"{slug}: template must invoke the image-side upload helper")

    print("plugin image workflow: path-filtered family selection, manual dispatch, amd64 build, and digest output verified")


if __name__ == "__main__":
    main()
