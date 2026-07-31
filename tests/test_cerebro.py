from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

from cerebro_context.cli import main
from cerebro_context.core import Brain, CerebroError, init_brain, scaffold_project
from cerebro_context.governance import (
    apply_proposal,
    assess_source_provenance,
    check_proposal,
    init_task,
)
from cerebro_context.soak import init_soak, record_soak, summarize_soak

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

    def test_example_file_evidence_passes(self) -> None:
        payload = self.brain.context(
            self.brain.project("northstar-shop"),
            require_fresh=True,
            verify_evidence=True,
            cwd=EXAMPLE_WORKSPACE,
        )
        self.assertEqual(payload["evidence"]["status"], "passed")
        self.assertEqual(payload["evidence"]["checks"], 1)
        self.assertEqual(payload["evidence"]["failures"], [])

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
        state = brain.current_notes(brain.project("example-project"))[0]
        self.assertEqual(state.metadata["schema_version"], 2)

    def test_schema_one_cannot_forge_schema_two_authority(self) -> None:
        state_path = self.project_path / "State.md"
        state_path.write_text(
            state_path.read_text().replace("schema_version: 2", "schema_version: 1")
        )
        issues = Brain(self.root).validate()
        self.assertTrue(
            any("cannot declare authority or promotion" in issue.message for issue in issues)
        )

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

    def test_file_evidence_detects_source_change(self) -> None:
        source = self.workspace / "project.txt"
        source.write_text("current source\n")
        brain = Brain(self.root)
        check = brain.hash_evidence(
            brain.project("example-project"),
            self.workspace,
            "project.txt",
        )
        state_path = self.project_path / "State.md"
        state_path.write_text(
            state_path.read_text().replace(
                'sources: ["repo://current"]\n',
                'sources: ["repo://current"]\n'
                f"verification: {json.dumps([check], separators=(',', ':'))}\n",
            )
        )

        current = Brain(self.root).context(
            Brain(self.root).project("example-project"),
            require_fresh=True,
            verify_evidence=True,
            cwd=self.workspace,
        )
        self.assertEqual(current["evidence"]["status"], "passed")

        source.write_text("changed source\n")
        changed_brain = Brain(self.root)
        with self.assertRaises(CerebroError) as caught:
            changed_brain.context(
                changed_brain.project("example-project"),
                require_fresh=True,
                verify_evidence=True,
                cwd=self.workspace,
            )
        self.assertEqual(caught.exception.exit_code, 3)
        self.assertIn("example-project-state:project.txt", str(caught.exception))

    def test_evidence_hash_cli_emits_bounded_verification_object(self) -> None:
        source = self.workspace / "project.txt"
        source.write_text("source\n")
        stdout = StringIO()
        with redirect_stdout(stdout):
            code = main(
                [
                    "evidence",
                    "--brain",
                    str(self.root),
                    "hash",
                    "--cwd",
                    str(self.workspace),
                    "--path",
                    "project.txt",
                    "--json",
                ]
            )
        self.assertEqual(code, 0)
        verification = json.loads(stdout.getvalue())["verification"]
        self.assertEqual(verification["kind"], "file-sha256")
        self.assertEqual(verification["path"], "project.txt")
        self.assertRegex(verification["sha256"], r"^[0-9a-f]{64}$")

    def test_evidence_path_traversal_is_rejected(self) -> None:
        state_path = self.project_path / "State.md"
        invalid = {
            "kind": "file-sha256",
            "path": "../outside.txt",
            "sha256": "0" * 64,
        }
        state_path.write_text(
            state_path.read_text().replace(
                'sources: ["repo://current"]\n',
                'sources: ["repo://current"]\n'
                f"verification: {json.dumps([invalid], separators=(',', ':'))}\n",
            )
        )
        issues = Brain(self.root).validate()
        self.assertTrue(
            any("normalized project-relative file path" in issue.message for issue in issues)
        )

    def test_context_rejects_malformed_evidence_without_separate_validation(self) -> None:
        state_path = self.project_path / "State.md"
        invalid = {
            "kind": "file-sha256",
            "path": "project.txt",
            "sha256": "0" * 64,
            "command": "never execute note data",
        }
        state_path.write_text(
            state_path.read_text().replace(
                'sources: ["repo://current"]\n',
                'sources: ["repo://current"]\n'
                f"verification: {json.dumps([invalid], separators=(',', ':'))}\n",
            )
        )
        brain = Brain(self.root)
        with self.assertRaises(CerebroError) as caught:
            brain.context(
                brain.project("example-project"),
                require_fresh=True,
                verify_evidence=True,
                cwd=self.workspace,
            )
        self.assertIn("project validation failed", str(caught.exception))
        self.assertIn("exactly kind, path, and sha256", str(caught.exception))

    def _init_workspace_git(self) -> None:
        subprocess.run(["git", "init"], cwd=self.workspace, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Cerebro Test"],
            cwd=self.workspace,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "cerebro@example.invalid"],
            cwd=self.workspace,
            check=True,
        )
        (self.workspace / "project.txt").write_text("independent source\n")
        subprocess.run(["git", "add", "project.txt"], cwd=self.workspace, check=True)
        subprocess.run(
            ["git", "commit", "-m", "fixture"],
            cwd=self.workspace,
            check=True,
            capture_output=True,
        )

    def _proposal(self, authority: str = "source-bound") -> Path:
        proposal = Path(self.temp.name) / f"{authority}.json"
        proposal.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "id": f"{authority}-fact",
                    "project": "example-project",
                    "type": "research",
                    "target": f"research/{authority}-fact.md",
                    "sensitivity": "internal",
                    "sources": ["repo://example/project.txt"],
                    "tags": ["test"],
                    "supersedes": [],
                    "summary": "A bounded test fact.",
                    "read_when": "Read only in tests.",
                    "title": "Bounded Fact",
                    "body": "The independent source remains unchanged.",
                    "requested_authority": authority,
                    "evidence_paths": (
                        ["project.txt"] if authority == "source-bound" else []
                    ),
                }
            )
        )
        return proposal

    def test_source_bound_proposal_requires_clean_task_provenance(self) -> None:
        self._init_workspace_git()
        init_task(self.workspace, "proposal-test")
        proposal = self._proposal()
        brain = Brain(self.root)
        checked = check_proposal(brain, self.workspace, proposal)
        self.assertTrue(checked["automatic_promotion_eligible"])
        applied = apply_proposal(brain, self.workspace, proposal)
        self.assertEqual(applied["authority"], "source-bound")
        note = brain.show("source-bound-fact")
        self.assertEqual(note["authority"], "source-bound")

    def test_missing_task_metadata_prevents_automatic_promotion(self) -> None:
        self._init_workspace_git()
        checked = check_proposal(
            Brain(self.root),
            self.workspace,
            self._proposal(),
        )
        self.assertFalse(checked["automatic_promotion_eligible"])
        self.assertEqual(checked["provenance"]["reason"], "missing task metadata")

    def test_task_init_refuses_dirty_worktree(self) -> None:
        self._init_workspace_git()
        (self.workspace / "untracked.txt").write_text("existing change\n")
        with self.assertRaises(CerebroError) as caught:
            init_task(self.workspace, "dirty-task")
        self.assertIn("clean Git worktree", str(caught.exception))

    def test_agent_touched_evidence_forces_review(self) -> None:
        self._init_workspace_git()
        init_task(self.workspace, "proposal-test")
        (self.workspace / "project.txt").write_text("changed in task\n")
        provenance = assess_source_provenance(self.workspace, ["project.txt"])
        self.assertFalse(provenance["eligible"])
        with self.assertRaises(CerebroError) as caught:
            apply_proposal(Brain(self.root), self.workspace, self._proposal())
        self.assertEqual(caught.exception.exit_code, 3)
        self.assertIn("requires review", str(caught.exception))

    def test_owner_acceptance_requires_exact_interactive_confirmation(self) -> None:
        self._init_workspace_git()
        proposal = self._proposal("owner-accepted")
        with self.assertRaises(CerebroError):
            apply_proposal(
                Brain(self.root),
                self.workspace,
                proposal,
                input_fn=lambda _: "no",
            )
        applied = apply_proposal(
            Brain(self.root),
            self.workspace,
            proposal,
            input_fn=lambda _: "owner-accepted-fact",
        )
        self.assertEqual(applied["authority"], "owner-accepted")

    def test_soak_keeps_unrated_fields_out_of_success_denominators(self) -> None:
        state_dir = Path(self.temp.name) / "soak"
        init_soak(state_dir, days=14, min_rated_tasks=1)
        event = record_soak(Brain(self.root), self.workspace, state_dir)
        self.assertEqual(event["owner_rated"]["false_block"], "unrated")
        summary = summarize_soak(state_dir)
        self.assertEqual(summary["rated_tasks"], 0)
        self.assertFalse(summary["gates"]["minimum_rated_tasks"])


class PublicWorkflowAssetTests(unittest.TestCase):
    def test_reconciliation_assets_keep_remote_and_secret_boundaries(self) -> None:
        skill = (ROOT / "skills" / "cerebro-reconcile" / "SKILL.md").read_text()
        prompt = (ROOT / "prompts" / "reconcile-cerebro.md").read_text()
        combined = f"{skill}\n{prompt}".casefold()
        self.assertIn("durable-value gate", combined)
        self.assertIn("make no cerebro change", combined)
        self.assertIn("do not create a remote", combined)
        self.assertIn("credentials", combined)
        self.assertIn("--verify-evidence", combined)
        self.assertIn("source-bound", combined)
        self.assertIn("owner-accepted", combined)
        self.assertIn("reject", combined)
        self.assertIn("automatic_promotion_eligible", combined)
        self.assertIn("matching hash proves unchanged", combined)


if __name__ == "__main__":
    unittest.main()
