import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
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

    def test_auto_reviews_cover_every_official_id_version_pair(self):
        steps = [
            {"id": "buz/example", "version": "1.9.0", "sha256": "sha-1.9"},
            {"id": "buz/example", "version": "1.10.0", "sha256": "sha-1.10"},
            {"id": "community/example", "version": "1.0.0", "sha256": "community"},
        ]
        args = type("Args", (), {"date": "2026-10-05", "commit": "abc123"})()
        with patch.object(self.gen_reviews, "load_index", return_value={
            (step["id"], step["version"]): step for step in steps
        }):
            entries = self.gen_reviews.auto_entries(args)
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


if __name__ == "__main__":
    unittest.main()
