from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .core import (
    Brain,
    CerebroError,
    __version__,
    default_brain_path,
    init_brain,
    render_human_documents,
    scaffold_project,
)
from .governance import apply_proposal, check_proposal, init_task
from .soak import (
    default_state_dir,
    init_soak,
    record_soak,
    summarize_soak,
)


def _add_brain(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--brain",
        type=Path,
        default=default_brain_path(),
        help="Cerebro root (default: CEREBRO_HOME or ~/.cerebro)",
    )


def _emit(payload: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if isinstance(payload, list):
        for item in payload:
            print(f"{item['id']}\t{item.get('summary', item.get('name', ''))}")
    elif isinstance(payload, dict) and "documents" in payload:
        print(render_human_documents(payload["documents"]))
    elif isinstance(payload, dict):
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cerebro",
        description="Verified operational context for coding agents.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Initialize an empty Cerebro brain")
    _add_brain(init)
    init.add_argument("--force", action="store_true", help="Replace only the root config")

    scaffold = sub.add_parser("scaffold", help="Create a project partition")
    _add_brain(scaffold)
    scaffold.add_argument("project_id")
    scaffold.add_argument("--name", required=True)
    scaffold.add_argument("--root", type=Path, required=True, help="Project working-tree root")

    projects = sub.add_parser("projects", help="List registered projects")
    _add_brain(projects)
    projects.add_argument("--json", action="store_true")

    resolve = sub.add_parser("resolve", help="Resolve a working directory to a project")
    _add_brain(resolve)
    resolve.add_argument("--cwd", type=Path, default=Path.cwd())
    resolve.add_argument("--json", action="store_true")

    validate = sub.add_parser("validate", help="Validate manifests, notes, and safety rules")
    _add_brain(validate)
    validate.add_argument("--json", action="store_true")

    doctor = sub.add_parser("doctor", help="Run a compact health check")
    _add_brain(doctor)
    doctor.add_argument("--json", action="store_true")

    context = sub.add_parser("context", help="Return authoritative project context")
    _add_brain(context)
    context.add_argument("--project")
    context.add_argument("--cwd", type=Path, default=Path.cwd())
    context.add_argument("--query", default="")
    context.add_argument("--history", action="store_true", help="Include labelled historical evidence")
    context.add_argument("--include-stale", action="store_true")
    context.add_argument("--require-fresh", action="store_true")
    context.add_argument(
        "--verify-evidence",
        action="store_true",
        help="Verify declared project-file SHA-256 checks",
    )
    context.add_argument("--restricted", action="store_true")
    context.add_argument("--json", action="store_true")

    search = sub.add_parser("search", help="Search current authority")
    _add_brain(search)
    search.add_argument("query")
    search.add_argument("--project")
    search.add_argument("--history", action="store_true")
    search.add_argument("--include-stale", action="store_true")
    search.add_argument("--restricted", action="store_true")
    search.add_argument("--json", action="store_true")

    show = sub.add_parser("show", help="Show a note by stable id")
    _add_brain(show)
    show.add_argument("note_id")
    show.add_argument("--allow-stale", action="store_true")
    show.add_argument("--restricted", action="store_true")
    show.add_argument("--json", action="store_true")

    evidence = sub.add_parser("evidence", help="Create deterministic evidence checks")
    _add_brain(evidence)
    evidence_sub = evidence.add_subparsers(dest="evidence_command", required=True)
    evidence_hash = evidence_sub.add_parser(
        "hash",
        help="Hash one project-relative regular file",
    )
    evidence_hash.add_argument("--cwd", type=Path, default=Path.cwd())
    evidence_hash.add_argument("--path", required=True)
    evidence_hash.add_argument("--json", action="store_true")

    task = sub.add_parser("task", help="Record task-base provenance")
    task_sub = task.add_subparsers(dest="task_command", required=True)
    task_init = task_sub.add_parser("init", help="Record the clean task base commit")
    task_init.add_argument("--cwd", type=Path, default=Path.cwd())
    task_init.add_argument("--id", required=True)
    task_init.add_argument("--json", action="store_true")

    proposal = sub.add_parser(
        "proposal",
        help="Check or apply a structured authority proposal",
    )
    _add_brain(proposal)
    proposal_sub = proposal.add_subparsers(dest="proposal_command", required=True)
    proposal_check = proposal_sub.add_parser(
        "check",
        help="Check promotion eligibility without changing the brain",
    )
    proposal_check.add_argument("--cwd", type=Path, default=Path.cwd())
    proposal_check.add_argument("--file", type=Path, required=True)
    proposal_check.add_argument("--json", action="store_true")
    proposal_apply = proposal_sub.add_parser(
        "apply",
        help="Apply an eligible proposal to the resolved project",
    )
    proposal_apply.add_argument("--cwd", type=Path, default=Path.cwd())
    proposal_apply.add_argument("--file", type=Path, required=True)
    proposal_apply.add_argument("--json", action="store_true")

    soak = sub.add_parser("soak", help="Record bounded personal workflow evidence")
    _add_brain(soak)
    soak.add_argument("--state-dir", type=Path, default=default_state_dir())
    soak_sub = soak.add_subparsers(dest="soak_command", required=True)
    soak_init = soak_sub.add_parser("init", help="Preregister a bounded soak")
    soak_init.add_argument("--days", type=int, default=14)
    soak_init.add_argument("--minimum-rated-tasks", type=int, default=20)
    soak_init.add_argument("--maximum-false-block-rate", type=float, default=0.05)
    soak_init.add_argument(
        "--maximum-repeated-explanation-rate",
        type=float,
        default=0.10,
    )
    soak_init.add_argument("--maximum-correction-rate", type=float, default=0.10)
    soak_init.add_argument("--maximum-median-upkeep-seconds", type=int, default=60)
    soak_init.add_argument("--json", action="store_true")
    soak_record = soak_sub.add_parser(
        "record",
        help="Record objective context signals and optional owner ratings",
    )
    soak_record.add_argument("--cwd", type=Path, default=Path.cwd())
    soak_record.add_argument(
        "--correction-needed",
        choices=("yes", "no", "unrated"),
        default="unrated",
    )
    soak_record.add_argument(
        "--repeated-explanation",
        choices=("yes", "no", "unrated"),
        default="unrated",
    )
    soak_record.add_argument(
        "--false-block",
        choices=("yes", "no", "unrated"),
        default="unrated",
    )
    soak_record.add_argument(
        "--useful-context",
        choices=("yes", "no", "unrated"),
        default="unrated",
    )
    soak_record.add_argument("--upkeep-seconds", type=int)
    soak_record.add_argument("--json", action="store_true")
    soak_summary = soak_sub.add_parser("summary", help="Summarize preregistered soak gates")
    soak_summary.add_argument("--json", action="store_true")
    return parser


def run(args: argparse.Namespace) -> int:
    payload: Any
    if args.command == "init":
        init_brain(args.brain, force=args.force)
        print(f"Initialized Cerebro at {args.brain.expanduser().resolve()}")
        return 0
    if args.command == "scaffold":
        target = scaffold_project(args.brain, args.project_id, args.name, args.root)
        print(f"Scaffolded {args.project_id} at {target}")
        return 0
    if args.command == "task":
        if args.task_command != "init":
            raise CerebroError(f"unsupported task command '{args.task_command}'")
        payload = init_task(args.cwd, args.id)
        _emit(payload, args.json)
        return 0

    brain = Brain(args.brain)
    if args.command == "projects":
        payload = [
            {
                "id": project.id,
                "name": project.name,
                "roots": project.roots,
                "sensitivity": project.sensitivity,
            }
            for project in brain.projects()
        ]
        _emit(payload, args.json)
        return 0
    if args.command == "resolve":
        project = brain.resolve(args.cwd)
        _emit({"id": project.id, "name": project.name, "path": str(project.path)}, args.json)
        return 0
    if args.command == "evidence":
        if args.evidence_command != "hash":
            raise CerebroError(f"unsupported evidence command '{args.evidence_command}'")
        project = brain.resolve(args.cwd)
        payload = {"verification": brain.hash_evidence(project, args.cwd, args.path)}
        _emit(payload, args.json)
        return 0
    if args.command == "proposal":
        if args.proposal_command == "check":
            payload = check_proposal(brain, args.cwd, args.file)
        elif args.proposal_command == "apply":
            payload = apply_proposal(brain, args.cwd, args.file)
        else:
            raise CerebroError(f"unsupported proposal command '{args.proposal_command}'")
        _emit(payload, args.json)
        return 0
    if args.command == "soak":
        state_dir = args.state_dir.expanduser()
        if args.soak_command == "init":
            payload = init_soak(
                state_dir,
                days=args.days,
                min_rated_tasks=args.minimum_rated_tasks,
                max_false_block_rate=args.maximum_false_block_rate,
                max_repeated_explanation_rate=args.maximum_repeated_explanation_rate,
                max_correction_rate=args.maximum_correction_rate,
                max_median_upkeep_seconds=args.maximum_median_upkeep_seconds,
            )
        elif args.soak_command == "record":
            payload = record_soak(
                brain,
                args.cwd,
                state_dir,
                correction_needed=args.correction_needed,
                repeated_explanation=args.repeated_explanation,
                false_block=args.false_block,
                useful_context=args.useful_context,
                upkeep_seconds=args.upkeep_seconds,
            )
        elif args.soak_command == "summary":
            payload = summarize_soak(state_dir)
        else:
            raise CerebroError(f"unsupported soak command '{args.soak_command}'")
        _emit(payload, args.json)
        return 0
    if args.command == "validate":
        issues = brain.validate()
        payload = {
            "status": "ok" if not issues else "failed",
            "issues": [
                {"path": issue.path, "line": issue.line, "message": issue.message}
                for issue in issues
            ],
        }
        _emit(payload, args.json)
        if not args.json:
            if issues:
                for issue in issues:
                    print(f"ERROR: {issue.render()}", file=sys.stderr)
            else:
                print("Cerebro validation passed.")
        return 0 if not issues else 2
    if args.command == "doctor":
        issues = brain.validate()
        payload = {
            "status": "healthy" if not issues else "unhealthy",
            "brain": str(brain.root),
            "projects": len(brain.projects()),
            "validation_issues": len(issues),
            "checks": {
                "config": brain.config_path.is_file(),
                "projects_directory": brain.projects_dir.is_dir(),
                "notes_valid": not issues,
            },
        }
        _emit(payload, args.json)
        return 0 if not issues else 2
    if args.command == "context":
        project = brain.project(args.project) if args.project else brain.resolve(args.cwd)
        payload = brain.context(
            project,
            query=args.query,
            include_history=args.history,
            include_stale=args.include_stale,
            require_fresh=args.require_fresh,
            restricted=args.restricted,
            verify_evidence=args.verify_evidence,
            cwd=args.cwd,
        )
        _emit(payload, args.json)
        return 0
    if args.command == "search":
        payload = brain.search(
            args.query,
            project_id=args.project,
            include_history=args.history,
            include_stale=args.include_stale,
            restricted=args.restricted,
        )
        _emit(payload, args.json)
        return 0
    if args.command == "show":
        payload = brain.show(
            args.note_id,
            allow_stale=args.allow_stale,
            restricted=args.restricted,
        )
        if args.json:
            _emit(payload, True)
        else:
            print(render_human_documents([payload]))
        return 0
    raise CerebroError(f"unsupported command '{args.command}'")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except CerebroError as exc:
        print(f"cerebro: {exc}", file=sys.stderr)
        return exc.exit_code
