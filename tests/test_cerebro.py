from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

from cerebro_context.cli import main
from cerebro_context.core import Brain, CerebroError, init_brain, scaffold_project

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_BRAIN = ROOT / "examples" / "northstar-shop" / "brain"
EXAMPLE_WORKSPACE = ROOT / "examples" / "northstar-shop" / "workspace"


def today() -> str:
    return datetime.now(UTC).date().isoformat()


class CerebroExampleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.brain = Brain(EXAMPLE_BRAIN)

    def test_example_validates(self) -> None:
        self.assertEqual(self.brain.validate(), [])

    def test_resolve_uses_longest_registered_root(self) -> None:
        project = self.brain.resolve(EXAMPLE_WORKSPACE)
        self.assertEqual(project.id, "northstar-shop")

    def test_context_returns_current_authority_and_excludes_stale(self) -> None:
        payload = self.brain.context(
            self.brain.project("northstar-shop"),
            require_fresh=True,
        )
        ids = {item["id"] for item in payload["documents"]}
        self.assertIn("northstar-shop-state", ids)
        self.assertIn("northstar-shop-agent-map", ids)
        self.assertIn("checkout-recovery-runbook", ids)
        self.assertNotIn("old-queue-evaluation", ids)
        self.assertEqual(payload["status"], "current")

    def test_stale_note_requires_explicit_opt_in(self) -> None:
        hidden = self.brain.search("intentionally stale")
        visible = self.brain.search("intentionally stale", include_stale=True)
        self.assertEqual(hidden, [])
        self.assertEqual(visible[0]["id"], "old-queue-evaluation")
        self.assertIn("warning", visible[0])

    def test_history_is_explicit_and_labelled(self) -> None:
        normal = self.brain.search("earlier checkout worker")
        history = self.brain.search("earlier checkout worker", include_history=True)
        self.assertEqual(normal, [])
        self.assertEqual(history[0]["partition"], "history")
        self.assertFalse(history[0]["current"])
        self.assertEqual(history[0]["warning"], "unverified historical evidence")

    def test_show_fails_closed_for_stale_note(self) -> None:
        with self.assertRaises(CerebroError) as caught:
            self.brain.show("old-queue-evaluation")
        self.assertEqual(caught.exception.exit_code, 3)
        shown = self.brain.show("old-queue-evaluation", allow_stale=True)
        self.assertFalse(shown["current"])

    def test_cli_emits_machine_readable_context(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            code = main(
                [
                    "context",
                    "--brain",
                    str(EXAMPLE_BRAIN),
                    "--project",
                    "northstar-shop",
                    "--require-fresh",
                    "--json",
                ]
            )
        self.assertEqual(code, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["project"], "northstar-shop")


class CerebroTemporaryBrainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "brain"
        self.workspace = Path(self.temp.name) / "workspace"
        self.workspace.mkdir()
        init_brain(self.root)
        self.project_path = scaffold_project(
            self.root,
            "example-project",
            "Example Project",
            self.workspace,
        )

    def test_scaffold_round_trip_validates(self) -> None:
        brain = Brain(self.root)
        self.assertEqual(brain.validate(), [])
        self.assertEqual(brain.resolve(self.workspace).id, "example-project")

    def test_require_fresh_fails_closed(self) -> None:
        config_path = self.root / "cerebro.json"
        config = json.loads(config_path.read_text())
        config["freshness_days"]["state"] = 1
        config_path.write_text(json.dumps(config))
        state_path = self.project_path / "State.md"
        state_path.write_text(
            state_path.read_text().replace(
                f"last_verified: {today()}",
                "last_verified: 2020-01-01",
            )
        )
        brain = Brain(self.root)
        with self.assertRaises(CerebroError) as caught:
            brain.context(brain.project("example-project"), require_fresh=True)
        self.assertEqual(caught.exception.exit_code, 3)
        self.assertIn("example-project-state", str(caught.exception))

    def test_secret_detection_does_not_echo_value(self) -> None:
        suspect = self.project_path / "research" / "Suspect.md"
        value = "synthetic-sensitive-value"
        suspect.write_text(
            "---\n"
            "schema_version: 1\n"
            "id: suspect-note\n"
            "project: example-project\n"
            "type: research\n"
            "status: current\n"
            f"created: {today()}\n"
            f"updated: {today()}\n"
            f"last_verified: {today()}\n"
            "sensitivity: internal\n"
            'sources: ["repo://example"]\n'
            "tags: []\n"
            "supersedes: []\n"
            'summary: "Synthetic safety test."\n'
            'read_when: "Read only in tests."\n'
            "---\n\n"
            "# Suspect\n\n"
            f"Password: {value}\n"
        )
        issues = Brain(self.root).validate()
        rendered = "\n".join(issue.render() for issue in issues)
        self.assertIn("credential-shaped value", rendered)
        self.assertNotIn(value, rendered)

    def test_duplicate_note_ids_are_rejected(self) -> None:
        original = self.project_path / "State.md"
        duplicate = self.project_path / "research" / "Duplicate.md"
        duplicate.write_text(original.read_text())
        issues = Brain(self.root).validate()
        self.assertTrue(any("duplicate note id" in issue.message for issue in issues))

    def test_restricted_note_requires_explicit_access(self) -> None:
        state_path = self.project_path / "State.md"
        state_path.write_text(state_path.read_text().replace("sensitivity: internal", "sensitivity: restricted"))
        brain = Brain(self.root)
        visible = brain.context(brain.project("example-project"))
        visible_ids = {item["id"] for item in visible["documents"]}
        self.assertNotIn("example-project-state", visible_ids)
        self.assertEqual(visible["status"], "partial")
        self.assertEqual(visible["warnings"][0]["count"], 1)
        with self.assertRaises(CerebroError) as caught:
            brain.context(brain.project("example-project"), require_fresh=True)
        self.assertEqual(caught.exception.exit_code, 4)
        restricted_ids = {
            item["id"]
            for item in brain.context(
                brain.project("example-project"), restricted=True
            )["documents"]
        }
        self.assertIn("example-project-state", restricted_ids)

    def test_cli_validation_failure_has_nonzero_exit(self) -> None:
        (self.project_path / "Agent Map.md").unlink()
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(["validate", "--brain", str(self.root), "--json"])
        self.assertEqual(code, 2)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "failed")

    def test_history_path_cannot_escape_brain(self) -> None:
        manifest_path = self.project_path / "project.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["history_paths"] = ["../../outside"]
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaises(CerebroError) as caught:
            Brain(self.root).projects()
        self.assertIn("must remain inside the brain", str(caught.exception))

    def test_malformed_collection_fields_fail_as_validation_issues(self) -> None:
        state_path = self.project_path / "State.md"
        state_path.write_text(
            state_path.read_text()
            .replace("type: state", 'type: ["state"]')
            .replace("sensitivity: internal", 'sensitivity: ["internal"]')
        )
        issues = Brain(self.root).validate()
        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("unsupported note type", messages)
        self.assertIn("sensitivity must be", messages)

    def test_duplicate_json_keys_are_rejected(self) -> None:
        manifest_path = self.project_path / "project.json"
        manifest_path.write_text(
            '{"schema_version":1,"schema_version":1,"id":"example-project",'
            '"name":"Example","roots":[],"sensitivity":"internal","history_paths":[]}'
        )
        with self.assertRaises(CerebroError) as caught:
            Brain(self.root).projects()
        self.assertIn("duplicate JSON key", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
