---
name: project-json-validator
description: >
  Validate a project.json file against the project-schema v0.1.0 specification.
  Use this skill whenever the user asks to "validate project.json", "check my project config",
  "is my project.json valid", or any request involving verifying a project.json file against
  the schema. Also trigger when another skill (like project-json-generator) needs to validate
  output it has produced. This skill checks both JSON Schema conformance and cross-reference
  rules that JSON Schema cannot express (unique names, unique ports, DAG dependencies,
  environment-override key validity, technology-stack mutual exclusion, etc.).
---

# Project JSON Validator

Validate a `project.json` file against the [project-schema v0.1.0](references/project-schema-v0_1_0.json)
specification. Reports both structural (JSON Schema) errors and semantic (cross-reference) errors.

## When to Use

- Validating an existing `project.json` file
- Validating output from the `project-json-generator` skill
- Checking a hand-edited `project.json` for correctness
- Debugging why a `project.json` is being rejected by tooling

## How to Run

```bash
python3 scripts/validate_project_json.py <path-to-project.json> \
  --schema references/project-schema-v0_1_0.json
```

The script requires the `jsonschema` Python package. It will auto-install via pip if missing.

### Exit Codes

- `0` — Valid (may have warnings)
- `1` — Errors found
- `2` — File or argument error

## What It Checks

### JSON Schema Validation
Validates the full document structure against the schema, including:
- Required fields at every level
- Enum values (lifecycle, CI platform, branching strategy, etc.)
- Version format patterns (three-part semver: `>=3.12.0`, not `>=3.12`)
- `additionalProperties: false` enforcement
- Nested `$ref` resolution for all `$defs`

### Cross-Reference Rules
Enforces constraints from the schema's `x-cross-reference-validation` that JSON Schema
cannot express:

| Rule | Severity | Description |
|---|---|---|
| `unique-project-names` | error | Every project name must be unique |
| `unique-project-ports` | error | Every project port must be unique |
| `dep-name-exists` | error | depends[]/consumes[] names must reference existing projects |
| `no-circular-depends` | error | depends[] graph must be a DAG |
| `env-override-key-exists` | error | environment-overrides keys must match global.environments |
| `technology-stack-resolved` | error | Every project must have a resolved technology stack |
| `technology-stack-mutual-exclusion` | error | Cannot define both technology-stack and technology-stack-overrides |
| `technology-stack-overrides-requires-global-default` | error | Overrides require a global default to exist |
| `unique-backing-service-ids` | error | Backing service IDs must be unique within each scope |
| `depends-on-non-active-lifecycle` | warning | Warn when depending on deprecated/archived projects |

## Interpreting Results

The validator outputs errors grouped by category (schema errors, then cross-reference
errors, then warnings). Each error includes the field path and a description.

If the user asks for help fixing errors, consult `references/tricky-fields.md` for
the correct types and enum values for commonly-misgenerated fields.

## Reference Files

- `references/project-schema-v0_1_0.json` — The canonical JSON Schema
- `references/tricky-fields.md` — Exact types, enum values, and version format rules
  for fields that are easy to get wrong. Consult this when helping users fix validation errors.
