import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class GenIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gen_index = load_script("gen_index")

    def test_index_paths_are_repo_relative_posix(self):
        self.assertEqual(
            self.gen_index.relative_file(ROOT / "plugins" / "thing.yaml", ROOT),
            "plugins/thing.yaml",
        )

    def test_index_rejects_plugin_paths_outside_repository(self):
        with self.assertRaisesRegex(SystemExit, "inside the repository root"):
            self.gen_index.relative_file(Path("/tmp/outside.yaml"), ROOT)

    def test_index_accepts_only_lowercase_two_segment_canonical_ids(self):
        path = ROOT / "plugins" / "fixture.yaml"
        self.assertEqual(
            self.gen_index.extract(
                self.gen_index.ID_RE, "id: buz/example-step\n", "id", path
            ),
            "buz/example-step",
        )
        for invalid_id in ("buz/net/example", "Buz/example", "buz/Example"):
            with self.subTest(invalid_id=invalid_id):
                with self.assertRaisesRegex(SystemExit, "missing top-level `id:`"):
                    self.gen_index.extract(
                        self.gen_index.ID_RE, f"id: {invalid_id}\n", "id", path
                    )

    def test_index_reads_only_explicit_category_and_supports_spaces(self):
        self.assertIsNone(self.gen_index.extract_category("id: buz/example\n"))
        self.assertEqual(
            self.gen_index.extract_category('id: buz/example\ncategory: "health check"\n'),
            "health check",
        )
        self.assertEqual(
            self.gen_index.extract_category("category: notifications_team\n"),
            "notifications_team",
        )
        self.assertEqual(
            self.gen_index.extract_category("category: notifications # grouping\n"),
            "notifications",
        )
        self.assertEqual(
            self.gen_index.extract_category('category: "health check" # grouping\n'),
            "health check",
        )
        with self.assertRaisesRegex(SystemExit, "simple label"):
            self.gen_index.extract_category("category: invalid/category\\n")

    def test_index_rejects_whitespace_only_category(self):
        with self.assertRaisesRegex(SystemExit, "simple label"):
            self.gen_index.extract_category("category:    ")

    def test_recursive_discovery_is_sorted_and_skips_hidden_paths_and_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested = root / "buz" / "object"
            nested.mkdir(parents=True)
            (root / "z.yaml").write_text("id: community/z\n")
            (nested / "1.0.0.yaml").write_text("id: buz/object\n")
            hidden = root / ".hidden"
            hidden.mkdir()
            (hidden / "hidden.yaml").write_text("id: community/hidden\n")
            outside = root.parent / f"{root.name}-linked.yaml"
            outside.write_text("id: community/linked\n")
            try:
                (root / "linked.yaml").symlink_to(outside)
                (root / "linked-dir").symlink_to(nested, target_is_directory=True)
                expected = ["buz/object/1.0.0.yaml", "z.yaml"]
                for script_name in ("gen_index", "egress", "lint_runs", "build_site"):
                    with self.subTest(script=script_name):
                        module = load_script(script_name)
                        files = module.discover_plugin_files(root)
                        self.assertEqual(
                            [path.relative_to(root).as_posix() for path in files],
                            expected,
                        )
            finally:
                outside.unlink(missing_ok=True)

    def test_nested_specs_with_same_basename_keep_distinct_indexed_paths(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            plugin_dir = Path(tmp) / "plugins"
            for name, step_id in (("alpha", "community/alpha"), ("beta", "community/beta")):
                spec_dir = plugin_dir / "buz" / name
                spec_dir.mkdir(parents=True)
                (spec_dir / "1.0.0.yaml").write_text(
                    f"id: {step_id}\nversion: 1.0.0\n"
                )
            files = self.gen_index.discover_plugin_files(plugin_dir)
            indexed = [self.gen_index.relative_file(path, ROOT) for path in files]
            expected_prefix = Path(tmp).relative_to(ROOT).as_posix()
        self.assertEqual(
            indexed,
            [
                f"{expected_prefix}/plugins/buz/alpha/1.0.0.yaml",
                f"{expected_prefix}/plugins/buz/beta/1.0.0.yaml",
            ],
        )


class EgressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.egress = load_script("egress")

    def test_nc_dynamic_host_and_port_are_reported(self):
        urls, hosts = self.egress.extract_egress(
            'nc -z -w 5 "$INPUT_HOST" "$INPUT_PORT"'
        )
        self.assertEqual(urls, [])
        self.assertIn("<dynamic-endpoint:host>", hosts)
        self.assertIn("<dynamic-endpoint:port>", hosts)

    def test_nc_inside_if_condition_reports_dynamic_host_and_port(self):
        _, hosts = self.egress.extract_egress(
            'if nc -z -w 5 "$INPUT_HOST" "$INPUT_PORT" 2>/dev/null; then echo up; fi'
        )
        self.assertEqual(
            hosts,
            ["<dynamic-endpoint:host>", "<dynamic-endpoint:port>"],
        )

    def test_network_commands_inside_command_substitutions_are_detected(self):
        for run in (
            'result=$(nc "$HOST" "$PORT")',
            'echo "$(nc example.com 443)"',
            'result=`nc example.com 443`',
        ):
            with self.subTest(run=run):
                _, hosts = self.egress.extract_egress(run)
                self.assertTrue(hosts, f"network command was missed in {run!r}")
        _, dynamic_hosts = self.egress.extract_egress('result=$(nc "$HOST" "$PORT")')
        self.assertIn("<dynamic-endpoint:host>", dynamic_hosts)
        self.assertIn("<dynamic-endpoint:port>", dynamic_hosts)

    def test_dynamic_non_input_variables_are_still_flagged(self):
        _, hosts = self.egress.extract_egress("if nc \"$TARGET\" \"$PORT\"; then :; fi")
        self.assertIn("<dynamic-endpoint:target>", hosts)
        self.assertIn("<dynamic-endpoint:port>", hosts)

    def test_literal_nc_host_and_port_are_reported(self):
        _, hosts = self.egress.extract_egress("nc -z -w 5 example.com 443")
        self.assertEqual(hosts, ["example.com:443"])

    def test_curl_variable_url_and_assigned_webhook_are_detected(self):
        run = 'URL="$INPUT_WEBHOOK"\ncurl -fsSL "$URL"'
        _, hosts = self.egress.extract_egress(run)
        self.assertIn("<dynamic-endpoint:webhook>", hosts)

    def test_literal_url_is_reported_without_shell_comment_text(self):
        urls, hosts = self.egress.extract_egress(
            'curl -fsSL https://example.com/health # nc fake.example 443'
        )
        self.assertEqual(urls, ["https://example.com/health"])
        self.assertEqual(hosts, ["example.com"])

    def test_timeout_and_env_wrappers_are_unwrapped(self):
        cases = {
            'timeout 5s env TOKEN=secret curl -fsSL https://api.example.test/ping':
                ["api.example.test"],
            'env -i -- timeout --signal=TERM 2s nc -z -w 1 example.test 443':
                ["example.test:443"],
            'timeout 3 env URL=https://service.example.test/health curl "$URL"':
                ["service.example.test"],
        }
        for run, expected in cases.items():
            with self.subTest(run=run):
                _, hosts = self.egress.extract_egress(run)
                self.assertEqual(hosts, expected)

    def test_unknown_timeout_wrapper_fails_closed_for_network_command(self):
        _, hosts = self.egress.extract_egress("timeout --unknown 5 nc example.test 443")
        self.assertIn("<unparsed-network-command>", hosts)

    def test_proxy_destinations_are_included_for_nc_and_ssh(self):
        _, nc_hosts = self.egress.extract_egress(
            "nc -x proxy.example.test:1080 -X 5 target.example.test 443"
        )
        self.assertEqual(nc_hosts, ["proxy.example.test:1080", "target.example.test:443"])
        _, ssh_hosts = self.egress.extract_egress(
            "ssh -J jump.example.test user@target.example.test uptime"
        )
        self.assertEqual(ssh_hosts, ["jump.example.test", "target.example.test"])
        _, option_hosts = self.egress.extract_egress(
            "ssh -o ProxyJump=jump2.example.test user@target2.example.test true"
        )
        self.assertEqual(option_hosts, ["jump2.example.test", "target2.example.test"])

    def test_proxy_endpoint_is_reported_for_curl(self):
        _, hosts = self.egress.extract_egress(
            "curl --proxy socks5h://proxy.example.test:1080 https://api.example.test"
        )
        self.assertEqual(hosts, ["api.example.test", "proxy.example.test:1080"])

        _, hosts = self.egress.extract_egress("ssh --mystery user@host.example.test")
        self.assertEqual(hosts, ["<unparsed-network-command>"])

        _, hosts = self.egress.extract_egress("ssh -p 2222 user@host.example.test echo proxy.example.test")
        self.assertEqual(hosts, ["host.example.test"])

    def test_assignment_runtime_endpoint_is_resolved_at_command_point(self):
        _, hosts = self.egress.extract_egress(
            'URL="$INPUT_WEBHOOK"\ncurl "$URL"\nURL="$INPUT_HOST"\ncurl "$URL"'
        )
        self.assertEqual(hosts, ["<dynamic-endpoint:host>", "<dynamic-endpoint:webhook>"])

    def test_endpoint_inputs_support_camel_case_names(self):
        self.assertTrue(self.egress._endpoint_input("apiBaseUrl"))
        self.assertTrue(self.egress._endpoint_input("proxyJumpHost"))
        self.assertFalse(self.egress._endpoint_input("retries"))

    def test_evidence_path_is_repo_relative_posix(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            plugin_dir = Path(tmp)
            (plugin_dir / "one.yaml").write_text(
                "id: community/one\nversion: 1.0.0\ninputs: {}\nrun: 'curl https://example.test'\n"
            )
            with patch.object(self.egress, "__file__", str(ROOT / "scripts" / "egress.py")):
                with patch.object(
                    sys,
                    "argv",
                    ["egress.py", "--plugins-dir", str(plugin_dir), "--print"],
                ):
                    with patch("builtins.print") as print_mock:
                        self.egress.main()
            printed = " ".join(str(call.args[0]) for call in print_mock.call_args_list)
            self.assertIn(plugin_dir.resolve().relative_to(ROOT).as_posix(), printed)
            self.assertNotIn(str(ROOT), printed)

    def test_aws_and_ossutil_endpoints_fail_closed_when_unresolved(self):
        cases = {
            'aws s3 cp file s3://bucket/key --endpoint-url "$INPUT_S3_ENDPOINT"':
                ["<dynamic-endpoint:endpoint>"],
            "AWS_ENDPOINT_URL=https://s3.example.test aws s3 ls": ["s3.example.test"],
            'ossutil cp file oss://bucket/key -e "$INPUT_OSS_ENDPOINT"':
                ["<dynamic-endpoint:endpoint>"],
            "ossutil cp file oss://bucket/key": ["<unparsed-network-command>"],
            "aws s3 ls": ["<unparsed-network-command>"],
        }
        for run, expected in cases.items():
            with self.subTest(run=run):
                _, hosts = self.egress.extract_egress(run)
                self.assertEqual(hosts, expected)

    def test_endpoint_input_allowlist_compares_exactly(self):
        evidence = [{
            "id": "buz/check",
            "egress_hosts": [],
            "endpoint_inputs": ["host", "port"],
        }]
        with tempfile.TemporaryDirectory() as tmp:
            allow = Path(tmp) / "allow.json"
            allow.write_text(json.dumps({"buz/check": {
                "hosts": [], "endpoint_inputs": ["host"]
            }}))
            violations = self.egress.check_allowlist(evidence, allow)
        self.assertTrue(any("port" in violation for violation in violations))


class PluginImageWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.checker = load_script("check_plugin_images")

    def test_digest_pin_updates_initial_template_without_changing_version(self):
        pin_script = load_script("pin_plugin_image")
        digest = "sha256:" + "a" * 64
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_dir = root / "plugins/buz/oss-upload"
            spec_dir.mkdir(parents=True)
            spec = spec_dir / "1.0.0.yaml"
            spec.write_text(
                "id: buz/oss-upload\nversion: 1.0.0\n"
                "source_repo: https://github.com/schiplat/buz-plugins/blob/master/plugins/buz/oss-upload/1.0.0.yaml\n"
                "engine: docker\nimage: docker.io/schiplat/buz-plugins-oss-tools:1.0.0\n"
            )
            self.assertEqual(pin_script.pin_spec(root, "oss-tools", digest), spec)
            updated = yaml.safe_load(spec.read_text())
            self.assertEqual(updated["version"], "1.0.0")
            self.assertEqual(updated["image"], f"docker.io/schiplat/buz-plugins-oss-tools@{digest}")
            self.assertIsNone(pin_script.pin_spec(root, "oss-tools", digest))

    def test_digest_pin_creates_patch_version_after_initial_pin(self):
        pin_script = load_script("pin_plugin_image")
        first_digest = "sha256:" + "a" * 64
        next_digest = "sha256:" + "b" * 64
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_dir = root / "plugins/buz/s3-upload"
            spec_dir.mkdir(parents=True)
            original = spec_dir / "1.0.0.yaml"
            original.write_text(
                "id: buz/s3-upload\nversion: 1.0.0\n"
                "source_repo: https://github.com/schiplat/buz-plugins/blob/master/plugins/buz/s3-upload/1.0.0.yaml\n"
                "engine: docker\nimage: docker.io/schiplat/buz-plugins-aws-tools@" + first_digest + "\n"
            )
            updated = pin_script.pin_spec(root, "aws-tools", next_digest)
            self.assertEqual(updated, spec_dir / "1.0.1.yaml")
            self.assertEqual(yaml.safe_load(original.read_text())["image"],
                             f"docker.io/schiplat/buz-plugins-aws-tools@{first_digest}")
            new_spec = yaml.safe_load(updated.read_text())
            self.assertEqual(new_spec["version"], "1.0.1")
            self.assertEqual(new_spec["image"], f"docker.io/schiplat/buz-plugins-aws-tools@{next_digest}")
            self.assertTrue(new_spec["source_repo"].endswith("/plugins/buz/s3-upload/1.0.1.yaml"))

    def test_digest_pin_rejects_invalid_digest_and_existing_tag_updates(self):
        pin_script = load_script("pin_plugin_image")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_dir = root / "plugins/buz/oss-upload"
            spec_dir.mkdir(parents=True)
            (spec_dir / "1.0.0.yaml").write_text(
                "id: buz/oss-upload\nversion: 1.0.0\n"
                "image: docker.io/schiplat/buz-plugins-oss-tools:1.0.4\n"
            )
            with self.assertRaisesRegex(SystemExit, "lowercase sha256"):
                pin_script.pin_spec(root, "oss-tools", "sha256:BAD")
            with self.assertRaisesRegex(SystemExit, "refusing to replace an existing non-initial image tag"):
                pin_script.pin_spec(root, "oss-tools", "sha256:" + "c" * 64)

    def test_workflow_publishes_only_changed_amd64_image_families(self):
        self.checker.main()
        workflow = yaml.safe_load((ROOT / ".github/workflows/publish-plugin-image.yml").read_text())
        triggers = workflow.get("on") or workflow.get(True)
        self.assertEqual(set(triggers), {"push"})
        self.assertEqual(triggers["push"]["branches"], ["master"])
        self.assertEqual(
            set(triggers["push"]["paths"]),
            {
                f"plugins/buz/{plugin}/image/**"
                for plugin in (
                    "oss-upload",
                    "s3-upload",
                    "setup-rust",
                    "setup-ruby",
                    "setup-php",
                    "setup-lua",
                    "setup-python",
                    "setup-node",
                    "setup-java",
                    "setup-go",
                )
            },
        )
        detect = workflow["jobs"]["detect"]
        select = next(step for step in detect["steps"] if step.get("id") == "select")
        self.assertNotIn("families+=(oss-tools aws-tools)", select["run"])
        self.assertIn("select_plugin_image_families.py", select["run"])
        self.assertEqual(detect["outputs"]["versions"], "${{ steps.select.outputs.versions }}")
        publish = workflow["jobs"]["publish"]
        self.assertEqual(publish["strategy"]["matrix"]["image_family"], "${{ fromJSON(needs.detect.outputs.families) }}")
        workflow_text = (ROOT / ".github/workflows/publish-plugin-image.yml").read_text()
        self.assertIn("fromJSON(needs.detect.outputs.versions)[matrix.image_family]", workflow_text)
        self.assertIn("${IMAGE_VERSION}-build.${GITHUB_RUN_NUMBER}.${GITHUB_RUN_ATTEMPT}", workflow_text)
        self.assertIn("Could not determine whether image tag exists; refusing to publish.", workflow_text)
        self.assertIn("platforms: linux/amd64", workflow_text)
        self.assertNotIn("linux/arm64", workflow_text)
        self.assertNotIn("setup-qemu-action", workflow_text)
        self.assertIn("${{ vars.DOCKERHUB_USERNAME }}", workflow_text)
        self.assertIn("${{ secrets.DOCKERHUB_TOKEN }}", workflow_text)
        self.assertNotIn("secrets.DOCKERHUB_USERNAME", workflow_text)
        self.assertIn("@1ca370b3a9802c92e886402e0dd88098a2533b12 # v6.4.1", workflow_text)
        pin = workflow["jobs"]["pin-template"]
        self.assertEqual(pin["needs"], ["detect", "publish"])
        self.assertEqual(pin["permissions"], {"contents": "write", "pull-requests": "write"})
        self.assertIn("always()", pin["if"])
        self.assertIn("needs.publish.result != 'cancelled'", pin["if"])
        self.assertIn("needs.detect.result == 'success'", pin["if"])
        self.assertIn("github.ref == 'refs/heads/master'", pin["if"])
        self.assertIn("BUZ_PLUGIN_GITHUB_PR_TOKEN || github.token", workflow_text)
        self.assertIn("gh pr create", workflow_text)
        self.assertIn("gh pr edit", workflow_text)
        self.assertNotIn("gh pr merge", workflow_text)
        self.assertIn('title="[skip image build] Pin OSS upload image digest"', workflow_text)
        self.assertIn('title="[skip image build] Pin S3 upload image digest"', workflow_text)
        selector = (ROOT / "scripts/select_plugin_image_families.py").read_text()
        self.assertIn("--first-parent", selector)
        self.assertIn("SKIP_MARKER", selector)
        upload = next(step for step in publish["steps"] if step.get("name") == "Upload published digest")
        self.assertEqual(upload["with"]["name"], "plugin-image-digest-${{ matrix.image_family }}")
        download = next(step for step in pin["steps"] if step.get("name") == "Download published digest")
        self.assertEqual(download["with"]["name"], "plugin-image-digest-${{ matrix.image_family }}")
        self.assertTrue(download.get("continue-on-error"))
        pin_prepare = next(step for step in pin["steps"] if step.get("name") == "Prepare template update")
        self.assertIn("git fetch origin master", pin_prepare["run"])
        self.assertIn("git switch -C \"$branch\" origin/master", pin_prepare["run"])

    def test_image_family_selector_matches_image_context_changes_only(self):
        selector = load_script("select_plugin_image_families")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", "-b", "master"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)

            def commit(path, content, message):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
                subprocess.run(["git", "add", path], cwd=root, check=True)
                subprocess.run(["git", "commit", "-m", message], cwd=root, check=True)
                return subprocess.run(
                    ["git", "rev-parse", "HEAD"], cwd=root, check=True,
                    capture_output=True, text=True,
                ).stdout.strip()

            before = commit("README.md", "root\n", "initial")
            # Template-only edits never rebuild an image (the digest does not
            # depend on the spec text) — yaml/yml changes select nothing.
            oss_spec = commit("plugins/buz/oss-upload/1.0.2.yaml", "version: 1.0.2\n", "bump OSS template")
            self.assertEqual(selector.select_families(root, before, oss_spec), [])
            s3_image = commit("plugins/buz/s3-upload/image/Dockerfile", "FROM scratch\n", "change S3 image")
            self.assertEqual(selector.select_families(root, oss_spec, s3_image), ["aws-tools"])
            skipped = commit(
                "plugins/buz/oss-upload/1.0.3.yaml", "version: 1.0.3\n",
                "[skip image build] Pin OSS upload image digest",
            )
            self.assertEqual(selector.select_families(root, s3_image, skipped), [])
            mixed_skip = commit(
                "plugins/buz/s3-upload/1.0.3.yaml", "version: 1.0.3\n",
                "[skip image build] Pin S3 upload image digest",
            )
            self.assertEqual(selector.select_families(root, s3_image, mixed_skip), [])
            (root / "plugins/buz/oss-upload/1.0.9.yaml").write_text("version: 1.0.9\n")
            (root / "plugins/buz/oss-upload/1.0.10.yaml").write_text("version: 1.0.10\n")
            (root / "plugins/buz/s3-upload/2.3.4.yaml").write_text("version: 2.3.4\n")
            self.assertEqual(selector.latest_template_version(root, "oss-tools"), "1.0.10")
            self.assertEqual(selector.latest_template_version(root, "aws-tools"), "2.3.4")
            with self.assertRaisesRegex(ValueError, "unsupported image family"):
                selector.latest_template_version(root, "missing-tools")

            branch_point = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, check=True,
                capture_output=True, text=True,
            ).stdout.strip()
            subprocess.run(["git", "switch", "-c", "pin-pr"], cwd=root, check=True)
            (root / "plugins/buz/s3-upload/1.0.4.yaml").write_text("version: 1.0.4\n")
            subprocess.run(["git", "add", "plugins/buz/s3-upload/1.0.4.yaml"], cwd=root, check=True)
            subprocess.run(
                ["git", "commit", "-m", "[skip image build] Pin S3 image digest"],
                cwd=root, check=True,
            )
            subprocess.run(["git", "switch", "master"], cwd=root, check=True)
            (root / "plugins/buz/oss-upload/1.0.5.yaml").write_text("version: 1.0.5\n")
            subprocess.run(["git", "add", "plugins/buz/oss-upload/1.0.5.yaml"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "normal OSS change"], cwd=root, check=True)
            normal_commit = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, check=True,
                capture_output=True, text=True,
            ).stdout.strip()
            subprocess.run(
                ["git", "merge", "--no-ff", "pin-pr", "-m", "[skip image build] Merge digest pin PR"],
                cwd=root, check=True,
            )
            merge_commit = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, check=True,
                capture_output=True, text=True,
            ).stdout.strip()
            # both commits in the merge range are template-only — nothing selects
            self.assertEqual(selector.select_families(root, branch_point, merge_commit), [])
            self.assertEqual(selector.select_families(root, normal_commit, merge_commit), [])

    def test_image_reference_accepts_expected_tag_or_sha256_pin(self):
        image = "docker.io/schiplat/buz-plugins-oss-tools"
        self.assertTrue(self.checker.image_reference_matches(image, f"{image}:1.0.0"))
        self.assertTrue(self.checker.image_reference_matches(image, f"{image}@sha256:{'a' * 64}"))
        for reference in (
            f"{image}:latest",
            f"{image}@sha256:{'A' * 64}",
            f"{image}@sha256:{'a' * 63}",
            "docker.io/other/image@sha256:" + "a" * 64,
        ):
            with self.subTest(reference=reference):
                self.assertFalse(self.checker.image_reference_matches(image, reference))

    def test_current_docker_releases_are_patch_bumped_and_digest_pinned(self):
        for plugin in ("oss-upload", "s3-upload"):
            with self.subTest(plugin=plugin):
                plugin_dir = ROOT / "plugins" / "buz" / plugin
                self.assertFalse((plugin_dir / "1.0.0.yaml").exists())
                current_path = plugin_dir / "1.0.2.yaml"
                current = yaml.safe_load(current_path.read_text())

                self.assertEqual(current["version"], "1.0.2")
                self.assertEqual(
                    current["source_repo"],
                    f"https://github.com/schiplat/buz-plugins/blob/master/plugins/buz/{plugin}/1.0.2.yaml",
                )
                self.assertIn("@sha256:", current["image"])

    def test_oss_entrypoint_uses_v2_environment_credentials(self):
        entrypoint = (ROOT / "plugins/buz/oss-upload/image/entrypoint.sh").read_text()
        for name in (
            "OSS_ACCESS_KEY_ID",
            "OSS_ACCESS_KEY_SECRET",
            "OSS_ENDPOINT",
            "OSS_REGION",
            "OSS_SESSION_TOKEN",
        ):
            self.assertIn(name, entrypoint)
        self.assertIn('exec ossutil cp "$SOURCE" "oss://$INPUT_BUCKET/$INPUT_OBJECT"', entrypoint)
        self.assertNotIn("--access-key-id", entrypoint)
        self.assertIn("/buz/workspace/*", entrypoint)
        dockerfile = (ROOT / "plugins/buz/oss-upload/image/Dockerfile").read_text()
        self.assertIn("OSSUTIL_SHA256_AMD64", dockerfile)
        self.assertIn("ossutil-${OSSUTIL_VERSION}-linux-amd64/ossutil", dockerfile)

    def test_s3_template_masks_credentials_and_uses_https_endpoint(self):
        spec = yaml.safe_load((ROOT / "plugins/buz/s3-upload/1.0.2.yaml").read_text())
        entrypoint = (ROOT / "plugins/buz/s3-upload/image/entrypoint.sh").read_text()
        for name in ("access_key_id", "secret_access_key", "session_token"):
            self.assertTrue(spec["inputs"][name].get("masking"))
        self.assertTrue(spec["inputs"]["endpoint_url"].get("required"))
        self.assertIn("AWS_ENDPOINT_URL", entrypoint)
        self.assertIn("https://", entrypoint)
        self.assertIn("/buz/workspace/*", entrypoint)
        dockerfile = (ROOT / "plugins/buz/s3-upload/image/Dockerfile").read_text()
        self.assertIn("COPY entrypoint.sh /usr/local/bin/buz-s3-upload", dockerfile)
        self.assertIn("awscli-exe-linux-x86_64-", dockerfile)
        self.assertIn("FB5DB77FD5C118B80511ADA8A6310ACC4672475C", dockerfile)
        self.assertEqual(spec["run"].strip(), "exec /usr/local/bin/buz-s3-upload")


class SitePathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build_site = load_script("build_site")
        cls.check_site_sources = load_script("check_site_sources")

    def test_nested_paths_map_uniquely_and_links_are_root_relative(self):
        files = [
            "plugins/buz/oss-upload/1.0.0.yaml",
            "plugins/buz/s3-upload/1.0.0.yaml",
            "plugins/community/oss-upload/1.0.0.yaml",
        ]
        pages = [self.build_site.template_filename(file) for file in files]
        self.assertEqual(
            pages,
            [
                "buz/oss-upload/1.0.0.html",
                "buz/s3-upload/1.0.0.html",
                "community/oss-upload/1.0.0.html",
            ],
        )
        self.assertEqual(len(set(pages)), len(pages))
        html = self.build_site.template_page_html({
            "id": "buz/oss-upload", "version": "1.0.0", "file": files[0],
            "engine": "shell", "content_sha256": "abc", "source_repo": None,
            "description": "English plugin summary.",
            "description_zh": "中文插件说明。",
            "inputs": [
                {"name": "source", "required": True},
                {"name": "destination", "required": False},
            ],
            "run": "internal implementation command",
        })
        self.assertIn('href="../../../favicon.svg"', html)
        self.assertIn('href="../../../style.css"', html)
        self.assertIn('href="../../../"', html)
        self.assertIn('<body class="template-page">', html)
        self.assertIn('<main class="wrap">', html)
        self.assertIn("uses: buz/oss-upload@1.0.0", html)
        self.assertIn("source: ", html)
        self.assertNotIn("internal implementation command", html)
        self.assertNotIn("中文插件说明", html)
        self.assertNotIn("lang='zh'", html)

    def test_source_checks_use_full_nested_page_path(self):
        self.assertEqual(
            self.check_site_sources.template_filename(
                "plugins/buz/oss-upload/1.0.0.yaml"
            ),
            "buz/oss-upload/1.0.0.html",
        )
        self.assertEqual(
            self.check_site_sources.template_filename("plugins/legacy.yaml"),
            "legacy.html",
        )

    def test_source_check_cli_verifies_nested_detail_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp)
            (dist / "templates" / "buz" / "oss-upload").mkdir(parents=True)
            source = "https://github.com/example/oss-upload"
            (dist / "site-data.json").write_text(json.dumps({"templates": [{
                "id": "buz/oss-upload", "file": "plugins/buz/oss-upload/1.0.0.yaml",
                "publisher": "official", "source_repo": source,
            }]}))
            page = dist / "templates" / "buz" / "oss-upload" / "1.0.0.html"
            page.write_text(f'<a href="{source}">Source repository</a>')
            with patch.object(sys, "argv", ["check_site_sources.py", "--dist-dir", str(tmp)]):
                with patch("builtins.print") as print_mock:
                    self.check_site_sources.main()
            self.assertIn("1/1", str(print_mock.call_args))

    def test_site_stages_nested_plugin_files_at_indexed_paths(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as source_tmp:
            source_root = Path(source_tmp)
            (source_root / "scripts").mkdir()
            (source_root / "index.json").write_text('{"steps": []}\n')
            plugin_dir = source_root / "plugins"
            nested = plugin_dir / "buz" / "oss-upload"
            nested.mkdir(parents=True)
            spec = nested / "1.0.0.yaml"
            spec.write_text(
                "id: buz/oss-upload\nversion: 1.0.0\nname: OSS upload\n"
                "publisher: official\nsource_repo: https://github.com/example/oss-upload\n"
            )
            newer_spec = nested / "1.0.1.yaml"
            newer_spec.write_text(
                "id: buz/oss-upload\nversion: 1.0.1\nname: OSS upload\n"
                "publisher: official\nsource_repo: https://github.com/example/oss-upload\n"
            )
            same_basename = plugin_dir / "community" / "oss-upload" / "1.0.0.yaml"
            same_basename.parent.mkdir(parents=True)
            same_basename.write_text(
                "id: community/oss-upload\nversion: 1.0.0\nname: Community OSS upload\n"
                "publisher: community\n"
            )
            output = Path(tempfile.mkdtemp())
            frontend_dist = Path(tempfile.mkdtemp())
            try:
                (frontend_dist / "style.css").write_text(
                    (ROOT / "frontend/public/style.css").read_text()
                )
                with patch.object(
                    self.build_site, "__file__", str(source_root / "scripts" / "build_site.py")
                ):
                    with patch.object(sys, "argv", [
                        "build_site.py", "--plugins-dir", str(plugin_dir),
                        "--out-dir", str(output), "--dist-dir", str(frontend_dist),
                    ]):
                        self.build_site.main()
                indexed_spec = spec.relative_to(source_root)
                staged_spec = output / indexed_spec
                self.assertTrue(
                    staged_spec.is_file(),
                    f"expected {staged_spec}, staged files: {sorted(str(p) for p in output.rglob('*'))}",
                )
                self.assertEqual(staged_spec.read_text(), spec.read_text())
                bundle = json.loads((output / "site-data.json").read_text())
                indexed_versions = [
                    (template["id"], template["version"])
                    for template in bundle["templates"]
                ]
                self.assertEqual(
                    indexed_versions,
                    [
                        ("buz/oss-upload", "1.0.0"),
                        ("buz/oss-upload", "1.0.1"),
                        ("community/oss-upload", "1.0.0"),
                    ],
                )
                for indexed in (spec, newer_spec):
                    indexed_path = indexed.relative_to(source_root).as_posix()
                    page_path = self.build_site.template_filename(indexed_path)
                    self.assertTrue((output / "templates" / page_path).is_file())
                    page_html = (output / "templates" / page_path).read_text()
                    self.assertIn(f"/templates/{page_path}", (output / "sitemap.xml").read_text())
                    self.assertIn('<body class="template-page">', page_html)
                    stylesheet_href = f"{self.build_site.page_relative_links(indexed_path)[2]}"
                    self.assertIn(f'href="{stylesheet_href}"', page_html)
                    self.assertTrue(
                        (output / "templates" / page_path).parent.joinpath(
                            stylesheet_href
                        ).resolve().is_file()
                    )
                self.assertIn(".template-page main.wrap", (output / "style.css").read_text())
                page_path = self.build_site.template_filename(
                    newer_spec.relative_to(source_root).as_posix()
                )
                self.assertIn("v1.0.1", (output / "templates" / page_path).read_text())
                community_indexed = same_basename.relative_to(source_root).as_posix()
                community_page_path = self.build_site.template_filename(community_indexed)
                self.assertTrue((output / "templates" / community_page_path).is_file())
            finally:
                import shutil
                shutil.rmtree(output, ignore_errors=True)
                shutil.rmtree(frontend_dist, ignore_errors=True)


class ReviewMergeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gen_reviews = load_script("gen_reviews")

    def test_manual_upsert_preserves_pinned_versions_and_unrelated_records(self):
        existing = [
            {"id": "author/step", "version": "1.0.0", "sha256": "old", "scope": "old", "source": "human"},
            {"id": "author/step", "version": "1.1.0", "sha256": "stale", "scope": "old", "source": "human"},
            {"id": "other/step", "version": "1.0.0", "sha256": "keep", "scope": "review", "source": "human"},
            {"id": "buz/official", "version": "1.0.0", "sha256": "ci", "source": "ci"},
        ]
        replacement = {"id": "author/step", "version": "1.1.0", "sha256": "new", "scope": "manual", "source": "human"}
        merged = self.gen_reviews.merge_reviews(existing, [replacement], keep_manual=False)
        self.assertEqual(merged[0], replacement)
        self.assertEqual(merged[1]["version"], "1.0.0")
        self.assertEqual([entry["id"] for entry in merged[1:]], ["author/step", "other/step", "buz/official"])

    def test_auto_tracks_blessed_ids_and_skips_new_official_ones(self):
        steps = [
            {"id": "buz/example", "version": "1.9.0", "sha256": "sha-1.9"},
            {"id": "buz/example", "version": "1.10.0", "sha256": "sha-1.10"},
            {"id": "buz/newcomer", "version": "1.0.0", "sha256": "sha-new"},
            {"id": "community/example", "version": "1.0.0", "sha256": "community"},
        ]
        args = type("Args", (), {"date": "2026-10-05", "commit": "abc123"})()
        existing = [
            {"id": "buz/example", "version": "1.0.0", "sha256": "old", "source": "ci"},
        ]
        with patch.object(self.gen_reviews, "load_index", return_value={
            (step["id"], step["version"]): step for step in steps
        }):
            entries = self.gen_reviews.auto_entries(args, existing)
        # buz/example is blessed — both versions stay fresh; buz/newcomer has
        # no review entry yet, so its first review must be manual.
        self.assertEqual(
            [(entry["id"], entry["version"], entry["sha256"]) for entry in entries],
            [
                ("buz/example", "1.10.0", "sha-1.10"),
                ("buz/example", "1.9.0", "sha-1.9"),
            ],
        )

    def test_manual_selection_uses_semver_not_lexicographic_order(self):
        steps = {
            ("buz/example", "1.9.0"): {
                "id": "buz/example", "version": "1.9.0", "sha256": "sha-1.9"
            },
            ("buz/example", "1.10.0"): {
                "id": "buz/example", "version": "1.10.0", "sha256": "sha-1.10"
            },
        }
        args = type("Args", (), {
            "ids": ["buz/example"],
            "date": "2026-10-05",
            "commit": "abc123",
            "scope": "manual review",
        })()
        with patch.object(self.gen_reviews, "load_index", return_value=steps):
            entries = self.gen_reviews.manual_entries(args)
        self.assertEqual(entries[0]["version"], "1.10.0")
        self.assertEqual(entries[0]["sha256"], "sha-1.10")

    def test_semver_sort_is_numeric(self):
        self.assertGreater(
            self.gen_reviews.semver_key("1.10.0"),
            self.gen_reviews.semver_key("1.9.0"),
        )

    def test_auto_upsert_preserves_existing_manual_review(self):
        existing = [
            {"id": "buz/official", "version": "1.0.0", "sha256": "stale", "source": "ci"},
            {"id": "author/step", "version": "1.0.0", "sha256": "human", "source": "human"},
        ]
        replacement = {"id": "buz/official", "version": "1.0.0", "sha256": "fresh", "source": "ci"}
        merged = self.gen_reviews.merge_reviews(existing, [replacement], keep_manual=True)
        self.assertEqual(merged, [replacement, existing[1]])

    def test_manual_merge_writes_atomically_and_retains_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reviews.json"
            existing = {"reviews": [{"id": "other/step", "version": "1", "sha256": "keep", "source": "human"}]}
            path.write_text(json.dumps(existing))
            with patch.object(self.gen_reviews, "resolve", return_value=path):
                self.gen_reviews.merge_and_write(
                    [{"id": "new/step", "version": "1", "sha256": "new", "source": "human"}],
                    keep_manual=False,
                )
            result = json.loads(path.read_text())
            self.assertEqual([r["id"] for r in result["reviews"]], ["new/step", "other/step"])
            self.assertEqual(list(Path(tmp).iterdir()), [path])


class PluginReadmeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.check = load_script("check_plugin_readmes")

    def test_plugin_dirs_collect_template_directories_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for path in (
                "buz/with-readme/1.0.0.yaml",
                "buz/with-readme/README.md",
                "buz/no-readme/1.0.0.yaml",
                "buz/with-readme/image/Dockerfile",
                ".hidden/1.0.0.yaml",
                "root-level.yaml",
            ):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("x\n")
            dirs = self.check.plugin_dirs(root)
            self.assertEqual(dirs, [root / "buz" / "no-readme", root / "buz" / "with-readme"])

    def test_missing_or_empty_readme_fails_and_present_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "buz" / "good").mkdir(parents=True)
            (root / "buz" / "good" / "1.0.0.yaml").write_text("x\n")
            (root / "buz" / "good" / "README.md").write_text("# good\n")
            (root / "buz" / "bad").mkdir(parents=True)
            (root / "buz" / "bad" / "1.0.0.yaml").write_text("x\n")
            with self.assertRaisesRegex(SystemExit, "1 plugin README\\(s\\) missing"):
                self.check.main([str(root)])
            (root / "buz" / "bad" / "README.md").write_text("# bad\n")
            (root / "buz" / "empty").mkdir(parents=True)
            (root / "buz" / "empty" / "1.0.0.yaml").write_text("x\n")
            (root / "buz" / "empty" / "README.md").write_text("   \n")
            with self.assertRaisesRegex(SystemExit, "1 plugin README\\(s\\) missing"):
                self.check.main([str(root)])
            (root / "buz" / "empty" / "README.md").write_text("# empty\n")
            self.check.main([str(root)])


if __name__ == "__main__":
    unittest.main()
