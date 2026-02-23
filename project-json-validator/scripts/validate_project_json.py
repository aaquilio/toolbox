#!/usr/bin/env python3
"""
Validate a project.json file against the project-schema and enforce
cross-reference rules that JSON Schema cannot express.

Usage:
    python3 validate_project_json.py <project.json> --schema <schema.json>

Exit codes:
    0 = valid (may have warnings)
    1 = errors found
    2 = file/argument error
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import jsonschema
    from jsonschema import Draft202012Validator, ValidationError
except ImportError:
    import subprocess as _sp
    _sp.check_call(
        [sys.executable, "-m", "pip", "install", "jsonschema", "--break-system-packages", "-q"],
        stdout=_sp.DEVNULL,
        stderr=_sp.DEVNULL,
    )
    import jsonschema
    from jsonschema import Draft202012Validator, ValidationError


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_schema(data: dict, schema: dict) -> list[str]:
    """Run JSON Schema validation. Returns list of error messages."""
    errors = []
    validator = Draft202012Validator(schema)
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
        path = ".".join(str(p) for p in error.absolute_path) or "(root)"
        errors.append(f"  {path}: {error.message}")
    return errors


def cross_reference_validate(data: dict) -> tuple[list[str], list[str]]:
    """
    Enforce cross-reference rules from x-cross-reference-validation.
    Returns (errors, warnings).
    """
    errors = []
    warnings = []

    projects = data.get("projects", [])
    global_cfg = data.get("global", {})
    environments = global_cfg.get("environments", [])
    has_global_tech_stack = "default-technology-stack" in global_cfg

    # Build lookup maps
    project_names = [p.get("name") for p in projects]
    project_by_name = {p.get("name"): p for p in projects}

    # Rule: unique-project-names
    seen_names = set()
    for name in project_names:
        if name in seen_names:
            errors.append(f"  unique-project-names: Duplicate project name '{name}'")
        seen_names.add(name)

    # Rule: unique-project-ports (base — not resolving env overrides for simplicity)
    seen_ports = {}
    for p in projects:
        port = p.get("port")
        if port is not None:
            if port in seen_ports:
                errors.append(
                    f"  unique-project-ports: Port {port} used by both "
                    f"'{seen_ports[port]}' and '{p.get('name')}'"
                )
            else:
                seen_ports[port] = p.get("name")

    # Rule: dep-name-exists + depends-on-non-active-lifecycle
    for p in projects:
        pname = p.get("name", "?")
        for dep_list_key in ("depends", "consumes"):
            for dep in p.get(dep_list_key, []):
                dep_name = dep.get("name")
                if dep_name not in project_by_name:
                    errors.append(
                        f"  dep-name-exists: {pname}.{dep_list_key} references "
                        f"'{dep_name}' which is not in projects[]"
                    )
                else:
                    target = project_by_name[dep_name]
                    lifecycle = target.get("lifecycle", "active")
                    if lifecycle in ("deprecated", "archived"):
                        warnings.append(
                            f"  depends-on-non-active-lifecycle: {pname}.{dep_list_key} "
                            f"references '{dep_name}' which has lifecycle '{lifecycle}'"
                        )

    # Rule: no-circular-depends (DFS cycle detection)
    adj = {p.get("name"): [d.get("name") for d in p.get("depends", [])] for p in projects}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {name: WHITE for name in project_names}

    def dfs(node, path):
        if node not in color:
            return
        color[node] = GRAY
        for neighbor in adj.get(node, []):
            if neighbor not in color:
                continue
            if color[neighbor] == GRAY:
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                errors.append(
                    f"  no-circular-depends: Cycle detected: {' → '.join(cycle)}"
                )
            elif color[neighbor] == WHITE:
                dfs(neighbor, path + [neighbor])
        color[node] = BLACK

    for name in project_names:
        if color.get(name) == WHITE:
            dfs(name, [name])

    # Rule: env-override-key-exists
    env_set = set(environments)
    for p in projects:
        pname = p.get("name", "?")
        for env_key in p.get("environment-overrides", {}).keys():
            if env_key not in env_set:
                errors.append(
                    f"  env-override-key-exists: {pname}.environment-overrides has key "
                    f"'{env_key}' which is not in global.environments {list(env_set)}"
                )

    # Rule: technology-stack-resolved
    for p in projects:
        pname = p.get("name", "?")
        has_project_stack = "technology-stack" in p
        has_project_overrides = "technology-stack-overrides" in p

        if not has_project_stack and not has_global_tech_stack:
            errors.append(
                f"  technology-stack-resolved: Project '{pname}' has no technology-stack "
                f"and no global.default-technology-stack exists"
            )

        # Rule: technology-stack-mutual-exclusion
        if has_project_stack and has_project_overrides:
            errors.append(
                f"  technology-stack-mutual-exclusion: Project '{pname}' defines both "
                f"technology-stack and technology-stack-overrides (only one allowed)"
            )

        # Rule: technology-stack-overrides-requires-global-default
        if has_project_overrides and not has_global_tech_stack:
            errors.append(
                f"  technology-stack-overrides-requires-global-default: Project '{pname}' "
                f"has technology-stack-overrides but no global.default-technology-stack exists"
            )

    # Rule: unique-backing-service-ids (per scope)
    def check_unique_backing_ids(scope_name, infra):
        if not infra:
            return
        services = infra.get("backing-services", [])
        seen_ids = set()
        for svc in services:
            sid = svc.get("id")
            if sid in seen_ids:
                errors.append(
                    f"  unique-backing-service-ids: Duplicate backing service id "
                    f"'{sid}' in {scope_name}"
                )
            seen_ids.add(sid)

    check_unique_backing_ids("global.infrastructure", global_cfg.get("infrastructure"))
    for p in projects:
        check_unique_backing_ids(
            f"projects['{p.get('name')}'].infrastructure",
            p.get("infrastructure")
        )

    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description="Validate project.json")
    parser.add_argument("project_json", help="Path to project.json")
    parser.add_argument("--schema", required=True, help="Path to JSON schema file")
    args = parser.parse_args()

    if not Path(args.project_json).exists():
        print(f"Error: {args.project_json} not found", file=sys.stderr)
        sys.exit(2)
    if not Path(args.schema).exists():
        print(f"Error: {args.schema} not found", file=sys.stderr)
        sys.exit(2)

    data = load_json(args.project_json)
    schema = load_json(args.schema)

    print(f"Validating {args.project_json}...\n")

    # 1. JSON Schema validation
    schema_errors = validate_schema(data, schema)
    if schema_errors:
        print(f"JSON Schema errors ({len(schema_errors)}):")
        for e in schema_errors:
            print(e)
        print()

    # 2. Cross-reference validation
    xref_errors, xref_warnings = cross_reference_validate(data)
    if xref_errors:
        print(f"Cross-reference errors ({len(xref_errors)}):")
        for e in xref_errors:
            print(e)
        print()

    if xref_warnings:
        print(f"Cross-reference warnings ({len(xref_warnings)}):")
        for w in xref_warnings:
            print(w)
        print()

    total_errors = len(schema_errors) + len(xref_errors)
    total_warnings = len(xref_warnings)

    if total_errors == 0:
        print(f"✅ Valid ({total_warnings} warning(s))")
        sys.exit(0)
    else:
        print(f"❌ Invalid — {total_errors} error(s), {total_warnings} warning(s)")
        sys.exit(1)


if __name__ == "__main__":
    main()
