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
    return parser


def run(args: argparse.Namespace) -> int:
    if args.command == "init":
        init_brain(args.brain, force=args.force)
        print(f"Initialized Cerebro at {args.brain.expanduser().resolve()}")
        return 0
    if args.command == "scaffold":
        target = scaffold_project(args.brain, args.project_id, args.name, args.root)
        print(f"Scaffolded {args.project_id} at {target}")
        return 0

    brain = Brain(args.brain)
    payload: Any
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
