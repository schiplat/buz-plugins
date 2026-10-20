import importlib.util
import json
import os
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
                    "docker",
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

    def test_toolchain_v1_1_is_a_run_harness_on_default_source_dir(self):
        plugin_names = (
            "setup-go",
            "setup-java",
            "setup-lua",
            "setup-node",
            "setup-php",
            "setup-python",
            "setup-ruby",
            "setup-rust",
        )
        ready_lines = {
            "setup-go": "go version",
            "setup-java": "java -version",
            "setup-lua": "lua -v",
            "setup-node": "node --version",
            "setup-php": "php --version",
            "setup-python": "python3 --version",
            "setup-ruby": "ruby --version",
            "setup-rust": "rustc --version",
        }
        for plugin in plugin_names:
            with self.subTest(plugin=plugin):
                spec = yaml.safe_load(
                    (ROOT / f"plugins/buz/{plugin}/1.1.0.yaml").read_text()
                )
                inputs = spec["inputs"]
                self.assertEqual(spec["default_dir"], "source")
                self.assertNotIn("script", inputs)
                self.assertNotIn("work_dir", inputs)
                self.assertNotIn("workdir", inputs)
                self.assertIn("version", inputs)
                run = spec["run"]
                self.assertNotIn("INPUT_SCRIPT", run)
                self.assertNotIn("mktemp", run)
                self.assertIn(ready_lines[plugin], run)

    def test_git_clone_v1_1_clones_into_and_prevents_overwrite(self):
        spec = yaml.safe_load(
            (ROOT / "plugins/buz/git-clone/1.1.0.yaml").read_text()
        )
        self.assertEqual(spec["inputs"]["into"]["default"], "source")
        self.assertNotIn("work_dir", spec["inputs"])
        self.assertNotIn("workdir", spec["inputs"])
        # git-clone keeps engine-default cwd: no default_dir of its own.
        self.assertIsNone(spec.get("default_dir"))
        run = spec["run"]
        self.assertIn('workspace_root="$(pwd -P)"', run)
        self.assertIn('into="${INPUT_INTO:-source}"', run)
        self.assertIn('if [ -e "$target" ] || [ -L "$target" ]; then', run)
        self.assertIn('git clone "$@" -- "$INPUT_REPO" "$target"', run)
        self.assertTrue(spec["inputs"]["token"]["masking"])

    def test_docker_v1_1_declares_capability_and_guards_credentials(self):
        spec = yaml.safe_load(
            (ROOT / "plugins/buz/docker/1.1.0.yaml").read_text()
        )
        self.assertEqual(spec["capabilities"], ["docker-socket"])
        self.assertEqual(spec["requires_buz"], ">=1.8.1")
        self.assertEqual(spec["default_dir"], "source")
        self.assertNotIn("work_dir", spec["inputs"])
        self.assertNotIn("workdir", spec["inputs"])
        run = spec["run"]
        for required in (
            'work_path="$(pwd -P)"',
            'DOCKER_CONFIG="$workspace_root/.docker"',
            "for guard_name in .docker .buz; do",
            "find -L \"$context_path\" \\( -name .docker -o -name .buz \\) -print",
            'context must not include DOCKER_CONFIG credentials',
            'docker info >/dev/null 2>&1',
        ):
            with self.subTest(guard=required):
                self.assertIn(required, run)

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
        self.assertNotIn("callout-warn", html)

    def test_explicit_buz_requirement_is_called_out_prominently(self):
        base = {
            "id": "buz/docker-compose", "version": "1.0.0",
            "file": "plugins/buz/docker-compose/1.0.0.yaml",
            "engine": "shell", "content_sha256": "abc", "source_repo": None,
            "description": "Compose deployment helper.",
            "inputs": [],
        }
        gated = self.build_site.template_page_html({**base, "requires_buz": ">=1.8.1"})
        ungated = self.build_site.template_page_html(base)

        # The gate is a prominent callout right under the description, not a
        # buried metadata line.
        self.assertIn("callout-warn", gated)
        self.assertIn("Requires Buz &gt;=1.8.1", gated)
        self.assertLess(
            gated.index("<p>Compose deployment helper.</p>"),
            gated.index("callout-warn"),
        )
        self.assertLess(gated.index("callout-warn"), gated.index("<h2>Inputs</h2>"))
        self.assertNotIn("Requires Buz", ungated)
        self.assertNotIn("callout-warn", ungated)

        # Structured data carries the requirement for crawlers.
        self.assertIn('"softwareRequirements": "Buz >=1.8.1"', gated)
        self.assertNotIn("softwareRequirements", ungated)

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


class DockerLoginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = yaml.safe_load(
            (ROOT / "plugins/buz/docker-login/1.1.0.yaml").read_text()
        )
        cls.registry = "registry.example.test"
        cls.username = "private-user-'\"$()"
        cls.password = "private-token-'\"$()`;\\multi\nline"

    def run_login(self, debug=None, exit_code=0, missing=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docker = root / "docker"
            docker.write_text(
                "#!/bin/sh\n"
                "printf '%s\\n' \"$@\" > \"$TEST_ARGS_FILE\"\n"
                "cat > \"$TEST_STDIN_FILE\"\n"
                "exit \"$TEST_DOCKER_EXIT\"\n"
            )
            docker.chmod(0o755)
            args_file = root / "args"
            stdin_file = root / "stdin"
            env = dict(os.environ)
            env.pop("INPUT_DEBUG", None)
            env.pop("ENV", None)
            env.pop("BASH_ENV", None)
            env.update({
                "PATH": f"{root}{os.pathsep}{os.defpath}",
                "HOME": str(root),
                "DOCKER_CONFIG": str(root / "docker-config"),
                "INPUT_REGISTRY": self.registry,
                "INPUT_USERNAME": self.username,
                "INPUT_PASSWORD": self.password,
                "TEST_ARGS_FILE": str(args_file),
                "TEST_STDIN_FILE": str(stdin_file),
                "TEST_DOCKER_EXIT": str(exit_code),
            })
            if debug is not None:
                env["INPUT_DEBUG"] = debug
            if missing is not None:
                env.pop(missing)
            result = subprocess.run(
                ["/bin/sh", "-c", self.spec["run"]],
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            args = args_file.read_text().splitlines() if args_file.exists() else None
            stdin = stdin_file.read_bytes() if stdin_file.exists() else None
        self.assertNotIn(self.username, result.stdout + result.stderr)
        self.assertNotIn(self.password, result.stdout + result.stderr)
        if args is not None:
            self.assertEqual(
                args, ["login", "--username", self.username, "--password-stdin", self.registry]
            )
            self.assertEqual(stdin, (self.password + "\n").encode())
        return result, args

    def test_debug_input_defaults_to_false_and_password_stays_masked(self):
        debug = self.spec["inputs"]["debug"]
        self.assertEqual(debug["type"], "boolean")
        self.assertEqual(debug["default"], "false")
        self.assertFalse(debug.get("required", False))
        self.assertTrue(self.spec["inputs"]["password"]["masking"])

    def test_debug_omitted_or_disabled_has_no_debug_output(self):
        for debug in (None, "false", "FALSE", ""):
            with self.subTest(debug=debug):
                result, args = self.run_login(debug)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIsNotNone(args)
                self.assertIn("docker login ok:", result.stdout)
                self.assertNotIn("[debug]", result.stdout + result.stderr)

    def test_debug_prints_redacted_command_and_exit_code(self):
        for debug in ("true", "TRUE", "True"):
            with self.subTest(debug=debug):
                result, _ = self.run_login(debug)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(
                    "[debug] command: docker login --username <redacted> --password-stdin "
                    + self.registry,
                    result.stdout,
                )
                self.assertIn("password: <redacted>, via stdin", result.stdout)
                self.assertIn("[debug] Docker config dir:", result.stdout)
                self.assertIn("[debug] docker login exit code: 0", result.stdout)

    def test_login_failure_preserves_exit_code_with_and_without_debug(self):
        for debug in (None, "false", "true"):
            with self.subTest(debug=debug):
                result, args = self.run_login(debug, exit_code=17)
                self.assertEqual(result.returncode, 17)
                self.assertIsNotNone(args)
                self.assertNotIn("docker login ok:", result.stdout)
                if debug == "true":
                    self.assertIn("[debug] docker login exit code: 17", result.stdout)
                else:
                    self.assertNotIn("[debug]", result.stdout + result.stderr)

    def test_invalid_debug_rejected_before_docker_runs(self):
        result, args = self.run_login("yes")
        self.assertEqual(result.returncode, 2)
        self.assertIn("debug must be true or false", result.stderr)
        self.assertIsNone(args)

    def test_missing_credentials_rejected_before_docker_runs(self):
        for missing in ("INPUT_REGISTRY", "INPUT_USERNAME", "INPUT_PASSWORD"):
            with self.subTest(missing=missing):
                result, args = self.run_login("true", missing=missing)
                self.assertNotEqual(result.returncode, 0)
                self.assertIsNone(args)
                self.assertIn("is required", result.stderr)


class WorkDirReleaseTests(unittest.TestCase):
    SETUP_PLUGINS = (
        "setup-rust", "setup-ruby", "setup-php", "setup-lua",
        "setup-python", "setup-node", "setup-java", "setup-go",
    )

    @classmethod
    def setUpClass(cls):
        cls.docker = yaml.safe_load((ROOT / "plugins/buz/docker/1.1.0.yaml").read_text())
        cls.clone = yaml.safe_load((ROOT / "plugins/buz/git-clone/1.1.0.yaml").read_text())

    def test_harness_releases_preserve_old_specs(self):
        for plugin in self.SETUP_PLUGINS:
            with self.subTest(plugin=plugin):
                old = yaml.safe_load((ROOT / f"plugins/buz/{plugin}/1.0.0.yaml").read_text())
                new = yaml.safe_load((ROOT / f"plugins/buz/{plugin}/1.1.0.yaml").read_text())
                self.assertEqual(old["version"], "1.0.0")
                self.assertEqual(old["inputs"]["workdir"]["default"], ".")
                self.assertEqual(new["version"], "1.1.0")
                self.assertEqual(new["default_dir"], "source")
                self.assertNotIn("workdir", new["inputs"])
                self.assertNotIn("script", new["inputs"])
                self.assertNotIn("work_dir", new["inputs"])
                self.assertNotIn("INPUT_SCRIPT", new["run"])
                self.assertNotIn("mktemp", new["run"])
                # the harness still selects the toolchain from the inputs
                self.assertIn("INPUT_VERSION", new["run"])
        old_docker = yaml.safe_load((ROOT / "plugins/buz/docker/1.0.0.yaml").read_text())
        old_clone = yaml.safe_load((ROOT / "plugins/buz/git-clone/1.0.0.yaml").read_text())
        self.assertEqual(old_docker["version"], "1.0.0")
        self.assertEqual(old_clone["inputs"]["dir"]["required"], True)

    def run_docker(self, workspace, step_dir="source", *, context="app", dockerfile="Dockerfile", docker_config=None, caller_run=""):
        # The engine chdirs into workspace/<step_dir> (step-level work_dir, else
        # default_dir) before the run block; emulate that with the cwd argument.
        mock_bin = workspace.parent / (workspace.name + "-bin")
        mock_bin.mkdir(exist_ok=True)
        args_log = workspace.parent / (workspace.name + "-docker.log")
        docker = mock_bin / "docker"
        docker.write_text(
            "#!/bin/sh\nprintf 'CALL' >> \"$DOCKER_LOG\"\n"
            "for arg do printf '\\t%s' \"$arg\" >> \"$DOCKER_LOG\"; done\n"
            "printf '\\tDOCKER_CONFIG=%s\\n' \"${DOCKER_CONFIG-}\" >> \"$DOCKER_LOG\"\n"
            "exit 0\n"
        )
        docker.chmod(0o755)
        run = self.docker["run"].replace("/buz/workspace", workspace.as_posix())
        if caller_run:
            run += "\n" + caller_run
        env = dict(os.environ)
        for key in list(env):
            if key.startswith("INPUT_"):
                env.pop(key)
        env.update({
            "PATH": f"{mock_bin}{os.pathsep}{os.defpath}", "HOME": str(workspace.parent / "home"),
            "DOCKER_LOG": str(args_log), "INPUT_TAGS": "registry.example/app:test",
            "INPUT_CONTEXT": context,
            "INPUT_DOCKERFILE": dockerfile, "INPUT_PUSH": "true",
        })
        if docker_config is not None:
            env["DOCKER_CONFIG"] = docker_config
        else:
            env.pop("DOCKER_CONFIG", None)
        result = subprocess.run(["/bin/sh", "-c", run], cwd=workspace / step_dir, env=env, capture_output=True, text=True, timeout=10)
        return result, args_log.read_text() if args_log.exists() else ""

    def test_docker_reuses_job_config_and_respects_explicit_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            app = workspace / "source/app"
            app.mkdir(parents=True)
            (app / "Dockerfile").write_text("FROM scratch\\n")
            (workspace / "source/Dockerfile").write_text("FROM scratch\\n")
            config = workspace / ".docker"
            config.mkdir()
            (config / "config.json").write_text('{"auths":{}}')
            result, log = self.run_docker(workspace)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"DOCKER_CONFIG={config.resolve()}", log)
            self.assertIn(str(app), log)
            explicit = str(Path(tmp) / "custom-docker-config")
            Path(explicit).mkdir()
            result, log = self.run_docker(workspace, docker_config=explicit)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"DOCKER_CONFIG={explicit}", log)

    def test_docker_composed_run_executes_caller_commands_after_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            app = workspace / "source/app"
            app.mkdir(parents=True)
            (app / "Dockerfile").write_text("FROM scratch\\n")
            (workspace / "source/Dockerfile").write_text("FROM scratch\\n")
            result, log = self.run_docker(
                workspace, caller_run="printf 'CALLER-RAN\\n' >> \"$DOCKER_LOG\""
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("CALL", log)
            self.assertLess(log.index("CALL"), log.index("CALLER-RAN"))

    def test_docker_rejects_job_root_and_credentials_contexts(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            app = workspace / "source/app"
            app.mkdir(parents=True)
            (app / "Dockerfile").write_text("FROM scratch\\n")
            config = workspace / ".docker"
            config.mkdir()
            (config / "config.json").write_text("secret")
            (app / "linked-docker").symlink_to(config, target_is_directory=True)
            result, log = self.run_docker(workspace)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("CALL", log)

    def test_docker_rejects_buz_directory_and_workspace_root_contexts(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            app = workspace / "source/app"
            app.mkdir(parents=True)
            (app / "Dockerfile").write_text("FROM scratch\\n")
            (workspace / ".buz").mkdir()
            (workspace / ".buz/env").write_text("TOKEN=secret\\n")
            (app / ".buz").symlink_to(workspace / ".buz", target_is_directory=True)
            result, log = self.run_docker(workspace)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("CALL", log)
            self.assertIn(".buz", result.stderr)
            result, log = self.run_docker(workspace, context="..")
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("CALL", log)

    def test_docker_rejects_dockerfile_symlink_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            workspace = base / "workspace"
            outside = base / "outside"
            outside.mkdir()
            (outside / "Dockerfile").write_text("FROM scratch\\n")
            source = workspace / "source"
            (source / "app").mkdir(parents=True)
            (source / "app/Dockerfile").symlink_to(outside / "Dockerfile")
            result, log = self.run_docker(workspace, dockerfile="app/Dockerfile")
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("CALL", log)

    def test_git_clone_safe_target_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            workspace = base / "workspace"
            workspace.mkdir()
            bin_dir = base / "bin"
            bin_dir.mkdir()
            log = base / "git.log"
            git = bin_dir / "git"
            git.write_text("#!/bin/sh\nprintf 'CALL' >> \"$GIT_LOG\"\nfor arg do printf '\\t%s' \"$arg\" >> \"$GIT_LOG\"; done\nprintf '\\n' >> \"$GIT_LOG\"\nexit 0\n")
            git.chmod(0o755)
            env = dict(os.environ)
            for key in list(env):
                if key.startswith("INPUT_"):
                    env.pop(key)
            env.update({"PATH": f"{bin_dir}{os.pathsep}{os.defpath}", "GIT_LOG": str(log), "INPUT_REPO": "https://example.test/repo.git", "INPUT_INTO": "nested/source", "INPUT_REF": "main", "INPUT_DEPTH": "1"})
            run = self.clone["run"]
            result = subprocess.run(["/bin/sh", "-c", run], cwd=workspace, env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((workspace / "nested").is_dir())
            self.assertIn("--depth\t1", log.read_text())
            self.assertIn("--branch\tmain", log.read_text())
            (workspace / "nested/source").mkdir()
            log.unlink()
            result = subprocess.run(["/bin/sh", "-c", run], cwd=workspace, env=env, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(log.exists())

    def test_git_clone_rejects_symlink_parent_outside_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            workspace = base / "workspace"
            workspace.mkdir()
            outside = base / "outside"
            outside.mkdir()
            (workspace / "linked").symlink_to(outside, target_is_directory=True)
            bin_dir = base / "bin"
            bin_dir.mkdir()
            git = bin_dir / "git"
            git.write_text("#!/bin/sh\nprintf called > \"$GIT_LOG\"\n")
            git.chmod(0o755)
            env = dict(os.environ)
            for key in list(env):
                if key.startswith("INPUT_"):
                    env.pop(key)
            env.update({"PATH": f"{bin_dir}{os.pathsep}{os.defpath}", "GIT_LOG": str(base / "git.log"), "INPUT_REPO": "https://example.test/repo.git", "INPUT_INTO": "linked/source"})
            result = subprocess.run(["/bin/sh", "-c", self.clone["run"]], cwd=workspace, env=env, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((base / "git.log").exists())


class LintRunsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lint = load_script("lint_runs")

    def test_top_level_exit_and_exec_are_flagged(self):
        body = [
            "set -e",
            "prepare-toolchain",
            "exit 0",
            "  exit 1",
            "if true; then exit 3; fi",
            "exec helper",
        ]
        offsets = self.lint.terminal_run_lines(body)
        self.assertEqual(offsets, [2, 5])

    def test_indented_and_empty_blocks_are_not_flagged(self):
        self.assertEqual(self.lint.terminal_run_lines(["case $v in\n  a) exit 2;;\nesac"]), [])
        self.assertEqual(self.lint.terminal_run_lines(["", "   "]), [])
        self.assertEqual(self.lint.terminal_run_lines(["# exit 0"]), [])

    def test_exception_allowlist_skips_fixed_entrypoint_templates(self):
        raw = "id: buz/oss-upload\nversion: 1.0.2\nrun: |\n  exec /usr/local/bin/buz-oss-upload\n"
        self.assertEqual(self.lint.spec_id(raw), "buz/oss-upload")
        self.assertIn("buz/oss-upload", self.lint.TERMINAL_RUN_EXCEPTIONS)
        self.assertIn("buz/http-check", self.lint.TERMINAL_RUN_EXCEPTIONS)

    def test_all_plugin_run_blocks_respect_the_terminal_run_rule(self):
        findings = []
        for path in self.lint.discover_plugin_files(ROOT / "plugins"):
            raw = path.read_text(encoding="utf-8")
            plugin_id = self.lint.spec_id(raw)
            for start, body in self.lint.run_blocks(raw):
                if plugin_id in self.lint.TERMINAL_RUN_EXCEPTIONS:
                    continue
                for offset in self.lint.terminal_run_lines(body):
                    findings.append(f"{path}:{start + offset + 1}")
        self.assertEqual(findings, [])


class CheckoutTests(unittest.TestCase):
    """buz/checkout@1.2.0 — the actions/checkout equivalent."""

    @classmethod
    def setUpClass(cls):
        cls.spec = yaml.safe_load((ROOT / "plugins/buz/checkout/1.2.0.yaml").read_text())
        cls.run_block = cls.spec["run"]

    def git(self, *args, cwd):
        return subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=30,
            env={**os.environ, "GIT_CONFIG_GLOBAL": self.git_config.as_posix()},
        )

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.git_config = base / "gitconfig"
        # Local submodule/file remotes mirror GitHub's fetch-by-SHA allowance.
        self.git_config.write_text(
            "[init]\n\tdefaultBranch = main\n"
            "[protocol \"file\"]\n\tallow = always\n"
            "[uploadpack]\n\tallowAnySHA1InWant = true\n"
        )
        self.base = base
        self.workspace = base / "workspace"
        self.workspace.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def make_origin(self):
        origin = self.base / "origin"
        origin.mkdir()
        self.git("init", "-q", cwd=origin)

        (origin / "a.txt").write_text("one\n")
        self.git("add", ".", cwd=origin)
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "one", cwd=origin)
        first = self.git("rev-parse", "HEAD", cwd=origin).stdout.strip()
        (origin / "b.txt").write_text("two\n")
        self.git("add", ".", cwd=origin)
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "two", cwd=origin)
        head = self.git("rev-parse", "HEAD", cwd=origin).stdout.strip()
        self.git("tag", "v1", cwd=origin)
        self.git("checkout", "-qb", "side", cwd=origin)
        (origin / "c.txt").write_text("side\n")
        self.git("add", ".", cwd=origin)
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "side", cwd=origin)
        self.git("checkout", "-q", "main", cwd=origin)
        # Server-side knob: mirrors GitHub's fetch-by-SHA allowance (must live
        # in the served repo, not the client's global config).
        self.git("config", "uploadpack.allowAnySHA1InWant", "true", cwd=origin)
        return origin, first, head

    def run_checkout(self, *, ref=None, depth=None, submodules=None, into=None,
                     buz_git_sha=None, cwd=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith("INPUT_")}
        env.update({
            # file:// honors --depth; plain local paths silently ignore it.
            "INPUT_REPO": (self.base / "origin").as_uri(),
            "HOME": self.base.as_posix(),
            "GIT_CONFIG_GLOBAL": self.git_config.as_posix(),
        })
        if ref is not None:
            env["INPUT_REF"] = ref
        if depth is not None:
            env["INPUT_DEPTH"] = depth
        if submodules is not None:
            env["INPUT_SUBMODULES"] = submodules
        if into is not None:
            env["INPUT_INTO"] = into
        if buz_git_sha is not None:
            env["BUZ_GIT_SHA"] = buz_git_sha
        return subprocess.run(
            ["/bin/sh", "-c", self.run_block], cwd=cwd or self.workspace,
            env=env, capture_output=True, text=True, timeout=60,
        )

    def head_info(self, target="source"):
        repo = self.workspace / target
        head = self.git("rev-parse", "HEAD", cwd=repo).stdout.strip()
        branch = self.git("rev-parse", "--abbrev-ref", "HEAD", cwd=repo).stdout.strip()
        count = self.git("rev-list", "--count", "HEAD", cwd=repo).stdout.strip()
        return head, branch, int(count)

    def test_shape_matches_the_release_contract(self):
        self.assertEqual(self.spec["id"], "buz/checkout")
        self.assertEqual(self.spec["version"], "1.2.0")
        self.assertEqual(self.spec["engine"], "shell")
        self.assertEqual(self.spec["requires_buz"], ">=1.8.1")
        self.assertIsNone(self.spec.get("default_dir"), "cwd is the workspace root")
        self.assertTrue(self.spec["inputs"]["repo"]["required"])
        self.assertTrue(self.spec["inputs"]["token"]["masking"])
        self.assertEqual(self.spec["inputs"]["into"]["default"], "source")
        self.assertEqual(self.spec["inputs"]["submodules"]["default"], "false")
        run = self.run_block
        for required in (
            'ref="${INPUT_REF:-${BUZ_GIT_SHA:-}}"',
            "checkout --detach FETCH_HEAD",
            "submodule update --init --recursive",
            "into already exists",
            "into parent resolves outside the Buz workspace",
        ):
            with self.subTest(fragment=required):
                self.assertIn(required, run)

    def test_default_clone_is_shallow_head(self):
        origin, first, head = self.make_origin()
        result = self.run_checkout()
        self.assertEqual(result.returncode, 0, result.stderr)
        got, branch, count = self.head_info()
        self.assertEqual(got, head)
        self.assertEqual(branch, "main")
        self.assertEqual(count, 1)

    def test_depth_zero_fetches_full_history(self):
        self.make_origin()
        result = self.run_checkout(depth="0")
        self.assertEqual(result.returncode, 0, result.stderr)
        _, _, count = self.head_info()
        self.assertEqual(count, 2)

    def test_branch_tag_and_sha_refs(self):
        origin, first, head = self.make_origin()
        result = self.run_checkout(ref="side", into="by-branch")
        self.assertEqual(result.returncode, 0, result.stderr)
        got, branch, _ = self.head_info("by-branch")
        self.assertEqual(branch, "side")

        result = self.run_checkout(ref="v1", into="by-tag")
        self.assertEqual(result.returncode, 0, result.stderr)
        got, _, _ = self.head_info("by-tag")
        tagged = self.git("rev-parse", "v1^{commit}", cwd=origin).stdout.strip()
        self.assertEqual(got, tagged)

        result = self.run_checkout(ref=head, into="by-sha")
        self.assertEqual(result.returncode, 0, result.stderr)
        got, branch, _ = self.head_info("by-sha")
        self.assertEqual(got, head)
        self.assertEqual(branch, "HEAD", "SHA checkout must detach")

        # Short hex abbreviations depend on server-side prefix support
        # (GitHub resolves them; plain git servers do not) — not asserted here.

    def test_buz_git_sha_is_the_default_ref(self):
        origin, first, head = self.make_origin()
        result = self.run_checkout(buz_git_sha=first, into="triggered")
        self.assertEqual(result.returncode, 0, result.stderr)
        got, _, _ = self.head_info("triggered")
        self.assertEqual(got, first, "webhook triggers must land on the triggering commit")
        # Explicit ref wins over the trigger context.
        result = self.run_checkout(ref="v1", buz_git_sha=first, into="explicit")
        self.assertEqual(result.returncode, 0, result.stderr)
        got, _, _ = self.head_info("explicit")
        tagged = self.git("rev-parse", "v1^{commit}", cwd=origin).stdout.strip()
        self.assertEqual(got, tagged)

    def test_submodules_recursive_populates_nested_repo(self):
        origin, _, _ = self.make_origin()
        lib = self.base / "lib"
        lib.mkdir()
        self.git("init", "-q", cwd=lib)
        (lib / "lib.txt").write_text("lib\n")
        self.git("add", ".", cwd=lib)
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "lib", cwd=lib)
        self.git("-c", "protocol.file.allow=always", "submodule", "add", "-q", lib.as_posix(), "vendor/lib", cwd=origin)
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "add submodule", cwd=origin)

        result = self.run_checkout(submodules="recursive", depth="0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.workspace / "source/vendor/lib/lib.txt").exists())

    def test_into_guards_still_apply(self):
        self.make_origin()
        (self.workspace / "source").mkdir()
        result = self.run_checkout()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("into already exists", result.stderr)

        result = self.run_checkout(into="../outside")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("into must be a non-empty relative checkout target", result.stderr)

        result = self.run_checkout(ref="abc", into="sha-check")
        self.assertNotEqual(result.returncode, 0, "3-hex ref is neither branch nor valid SHA length")
        self.assertIn("7-40 hex", result.stderr)


if __name__ == "__main__":
    unittest.main()


class PluginRequestWishlistTests(unittest.TestCase):
    """The plugin-request wishlist: issue template + marketplace wiring."""

    def test_issue_template_shape(self):
        spec = yaml.safe_load(
            (ROOT / ".github/ISSUE_TEMPLATE/plugin_request.yml").read_text()
        )
        self.assertEqual(spec["name"], "Plugin request / 插件需求征集")
        self.assertEqual(spec["labels"], ["wishlist"])
        fields = {entry.get("id"): entry for entry in spec["body"] if "id" in entry}
        self.assertIn("name", fields)
        self.assertIn("what", fields)
        self.assertEqual(fields["what"]["validations"]["required"], True)
        contribute = fields["contribute"]
        self.assertEqual(contribute["validations"]["required"], True)
        options = contribute["attributes"]["options"]
        self.assertTrue(any("official buz/ namespace" in o for o in options))
        self.assertTrue(any("own namespace" in o for o in options))
        # A pointer to the namespace policy so requesters know the bar.
        body_text = "\n".join(
            entry.get("attributes", {}).get("value", "") for entry in spec["body"]
        )
        self.assertIn("Namespace policy", body_text)

    def test_marketplace_front_end_links_the_wishlist(self):
        types = (ROOT / "frontend/src/types.ts").read_text()
        self.assertIn("template=plugin_request.yml", types)
        app = (ROOT / "frontend/src/App.vue").read_text()
        self.assertIn("REQUEST_PLUGIN_URL", app)
        self.assertIn("T.request", app)
        ui = (ROOT / "frontend/src/ui-text.ts").read_text()
        self.assertIn("Request a plugin", ui)
