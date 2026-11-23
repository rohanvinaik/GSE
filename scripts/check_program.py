#!/usr/bin/env python3
"""Verify the pinned three-repository program without interpreting its prose."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPOSITORIES = ("sparse-wiki-grounding", "gse", "Regenesis")


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _cycle_errors(dependencies: dict[str, list[str]]) -> list[str]:
    state: dict[str, int] = {}
    errors: list[str] = []

    def visit(node: str, chain: tuple[str, ...]) -> None:
        current = state.get(node, 0)
        if current == 2:
            return
        if current == 1:
            errors.append("dependency cycle: " + " -> ".join((*chain, node)))
            return
        state[node] = 1
        for dependency in dependencies[node]:
            if dependency in dependencies:
                visit(dependency, (*chain, node))
        state[node] = 2

    for package in dependencies:
        visit(package, ())
    return errors


def check(base: Path, local_only: bool) -> list[str]:
    errors: list[str] = []
    selected = (Path(__file__).resolve().parents[1].name,) if local_only else REPOSITORIES
    reference_by_id: dict[str, tuple[str, str]] = {}
    reference_by_path: dict[str, str] = {}
    dependencies: dict[str, list[str]] = {}
    shared_digests: dict[str, str] = {}
    roots = {name: base / name for name in selected}

    for name, root in roots.items():
        program = root / "docs" / "program"
        if not program.is_dir():
            errors.append(f"{name}: missing program directory {program}")
            continue
        if not (root / "openspec" / "config.yaml").is_file():
            errors.append(f"{name}: missing OpenSpec configuration")
        if not (root / ".github" / "ISSUE_TEMPLATE" / "program-work.yml").is_file():
            errors.append(f"{name}: missing program issue form")
        for relative in (
            "docs/program/EXECUTION_WORKFLOW.md",
            "scripts/check_program.py",
            ".github/ISSUE_TEMPLATE/program-work.yml",
        ):
            shared = root / relative
            if shared.is_file():
                digest = hashlib.sha256(shared.read_bytes()).hexdigest()
                previous = shared_digests.setdefault(relative, digest)
                if previous != digest:
                    errors.append(f"{name}: shared program file diverged: {relative}")
        for required in (
            "START_HERE.md",
            "GLOSSARY.md",
            "BUILD_GAPS.md",
            "BUILD_SPEC.md",
            "ASSURANCE.md",
            "EXECUTION_WORKFLOW.md",
        ):
            if not (program / required).is_file():
                errors.append(f"{name}: missing {required}")
        try:
            manifest = _json(program / "REFERENCE_MANIFEST.json")
            index = _json(program / "WORK_INDEX.json")
        except (OSError, ValueError) as exc:
            errors.append(f"{name}: cannot load manifest or work index: {exc}")
            continue
        if manifest.get("schema_version") != 1 or index.get("schema_version") != 1:
            errors.append(f"{name}: unsupported manifest/index schema")
        if index.get("repo") != name:
            errors.append(f"{name}: work index repo field differs from directory name")

        for reference in manifest.get("references", []):
            ref_id = reference.get("id", "")
            path = Path(reference.get("path", ""))
            declared_hash = reference.get("sha256", "")
            if not ref_id or not path.is_absolute() or len(declared_hash) != 64:
                errors.append(f"{name}: malformed reference {ref_id!r}")
                continue
            key = (str(path), declared_hash)
            previous = reference_by_id.setdefault(ref_id, key)
            if previous != key:
                errors.append(f"{name}: inconsistent shared reference {ref_id}")
            previous_hash = reference_by_path.setdefault(str(path), declared_hash)
            if previous_hash != declared_hash:
                errors.append(f"{name}: inconsistent hash for shared path {path}")
            if not path.is_file():
                errors.append(f"{name}: UNAVAILABLE_REFERENCE {ref_id}: {path}")
            else:
                actual = hashlib.sha256(path.read_bytes()).hexdigest()
                if actual != declared_hash:
                    errors.append(f"{name}: CHANGED_REFERENCE {ref_id}: {path}")
            for citation in reference.get("cited_by", []):
                if not (program / citation).is_file():
                    errors.append(f"{name}: {ref_id} cites missing program file {citation}")

        for package in index.get("packages", []):
            package_id = package.get("id", "")
            if not package_id or package_id in dependencies:
                errors.append(f"{name}: missing or duplicate package ID {package_id!r}")
                continue
            dependencies[package_id] = list(package.get("depends_on", []))
            spec = package.get("spec", "").split("#", 1)[0]
            if not spec or not (program / spec).is_file():
                errors.append(f"{name}: {package_id} points to missing spec {spec!r}")
        issue_path = program / "ISSUE_MAP.json"
        if issue_path.is_file():
            try:
                issue_map = _json(issue_path)
            except (OSError, ValueError) as exc:
                errors.append(f"{name}: cannot load issue map: {exc}")
            else:
                local_ids = {item.get("id") for item in index.get("packages", [])}
                mapped_ids = set(issue_map.get("issues", {}))
                if issue_map.get("schema_version") != 1 or local_ids != mapped_ids:
                    errors.append(f"{name}: issue map does not match work index")
                for package_id, url in issue_map.get("issues", {}).items():
                    if not url.startswith("https://github.com/rohanvinaik/"):
                        errors.append(f"{name}: invalid issue URL for {package_id}")

    for package, required in dependencies.items():
        for dependency in required:
            if dependency not in dependencies and not local_only:
                errors.append(f"{package}: missing dependency {dependency}")
    errors.extend(_cycle_errors(dependencies))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local", action="store_true", help="check this repository only")
    args = parser.parse_args()
    base = Path(__file__).resolve().parents[2]
    errors = check(base, args.local)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    scope = "local" if args.local else "three-repository"
    print(f"Program references and dependency graph verified ({scope}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
