---
name: project-json-generator
description: >
  Examine a project or monorepo directory and generate a project.json configuration file
  that conforms to the project-schema v0.1.0 spec. Use this skill whenever the user asks to
  "generate a project.json", "describe this project", "create a project config", "map this
  repo", or any request that involves producing a structured project manifest from an existing
  codebase. Also trigger when the user mentions "project schema", "project-schema", or wants
  to catalog the technology stack, dependencies, infrastructure, CI/CD, testing, or
  observability setup of a project by examining its files. Even if the user just says
  "scan this project" or "what's in this repo", consider triggering this skill.
---

# Project JSON Generator

Generate a `project.json` configuration file by examining a project directory. The output
conforms to project-schema v0.1.0 and serves as the single source of truth for all
technology decisions in the project or monorepo.

## Before You Start

1. Read the schema's `x-agent-guide` section in `references/project-schema-v0_1_0.json`
   to understand key concepts like config resolution, depends vs consumes, and lifecycle.
2. Read `references/discovery-guide.md` for the file-to-field mapping table — it tells
   you exactly which files to look for and what schema fields they inform.
3. Read `references/tricky-fields.md` for exact types, enum values, and version format
   rules for fields that are easy to get wrong.

## Workflow

### Phase 1 — Discovery

Scan the project root to build a mental model of the codebase. Run these commands
(adapt as needed) and collect the results:

```bash
# Find config files (2 levels deep)
find . -maxdepth 2 -type f \
  \( -name 'package.json' -o -name 'tsconfig*.json' -o -name '*.csproj' \
     -o -name 'go.mod' -o -name 'Cargo.toml' -o -name 'pyproject.toml' \
     -o -name 'pom.xml' -o -name 'build.gradle*' -o -name 'Gemfile' \
     -o -name 'Dockerfile*' -o -name 'docker-compose*.yml' \
     -o -name '.eslintrc*' -o -name '.prettierrc*' -o -name 'biome.json*' \
     -o -name 'jest.config*' -o -name 'vitest.config*' -o -name 'pytest.ini' \
     -o -name '.github' -o -name '.gitlab-ci.yml' \
     -o -name 'Jenkinsfile' -o -name 'Makefile' -o -name 'turbo.json' \
     -o -name 'nx.json' -o -name 'pnpm-workspace.yaml' -o -name 'lerna.json' \
     -o -name '.env.example' -o -name 'openapi*.yaml' -o -name 'openapi*.json' \
     -o -name '.snyk' -o -name '.semgreprc*' -o -name '.trivy*' \
  \) 2>/dev/null | head -200

# Top-level listing for monorepo detection
ls -1a .

# Root manifest
cat package.json 2>/dev/null || cat pyproject.toml 2>/dev/null || cat go.mod 2>/dev/null

# CI workflows
ls .github/workflows/ 2>/dev/null && head -100 .github/workflows/*.yml 2>/dev/null
cat .gitlab-ci.yml 2>/dev/null | head -100
```

Collect additional files as indicated by `references/discovery-guide.md`.

**Monorepo detection**: If you find workspace indicators (pnpm-workspace.yaml, turbo.json,
nx.json, lerna.json, or `workspaces` in package.json), treat the repo as a monorepo.
Scan each workspace member as a separate project entry.

### Phase 2 — Inference

Map discovered files to schema fields. For each schema section:

1. **metadata** — Infer `name` from root package.json `name` field, directory name, or
   git remote. `type` is `monorepo` if workspaces detected, otherwise `standalone`.
   `description` from package.json `description` or README first paragraph.

2. **global.default-technology-stack** — Infer `language`, `version`, `runtime`,
   `package-manager`, and `frameworks` from the root manifest and config files.
   Use version ranges (e.g. `^20.0.0`) not exact pins unless only exact versions
   are discoverable.

3. **global.environments** — Look for environment-specific config files, CI stages,
   docker-compose profiles, or `.env.*` files. Default to `["development", "staging", "production"]`
   if nothing more specific is found.

4. **global sections** (ci-cd, testing, code-quality, security, observability,
   service-communication, release, dependencies, deployment, api) — See
   `references/discovery-guide.md` for which files map to which fields.

5. **projects[]** — For each project/service/library detected:
   - `name`: directory name or package name
   - `path`: relative path from repo root
   - `type`: infer from context (app, service, frontend, worker, library, cli, gateway, job)
   - `description`: from its package.json or README
   - `owner.team`: **ASK the user** — this is required and cannot be inferred
   - `version`: from its package.json or manifest
   - `lifecycle`: default to `"active"` unless clear signals otherwise (e.g. DEPRECATED in README)
   - `port`: from Dockerfile EXPOSE, docker-compose ports, or server config
   - `depends` / `consumes`: infer from internal imports, workspace references, docker-compose depends_on
   - `technology-stack` or `technology-stack-overrides`: only if the project differs from the global default

### Phase 3 — Gather Missing Required Fields

Some required fields cannot be reliably inferred. Ask the user for these **in a single batch**,
not one-at-a-time. Present a numbered list grouped by category so the user can answer in one
response. Example:

> I need a few things I couldn't determine from the codebase:
> 1. What team owns this project? (kebab-case slug, e.g. `backend-platform`)
> 2. What branching strategy do you use? (trunk-based / gitflow / github-flow / gitlab-flow / release-flow)
> 3. ...

Fields that commonly need asking:
- `owner.team` for each project (unless there's a CODEOWNERS file to extract from)
- Any required global fields where the codebase gives no signal (e.g., the repo has
  no CI config at all — ask which platform they use)
- `version-control.branching-strategy` if not inferable from CI config

Skip all optional fields that lack evidence in the codebase. Do not invent values.

### Phase 4 — Validation

**If the `project-json-validator` skill is available**, use it to validate the assembled JSON:

```bash
python3 <project-json-validator>/scripts/validate_project_json.py project.json \
  --schema <project-json-validator>/references/project-schema-v0_1_0.json
```

Fix any validation errors automatically if possible. If not, report them to the user.

**If the `project-json-validator` skill is not available**, skip automated validation.
Instead, carefully review the output against the rules in `references/tricky-fields.md`
to catch common mistakes before presenting the result.

### Phase 5 — Output

Write `project.json` to the project root directory. Present it to the user with a brief
summary of:
- How many projects were detected
- Key technology decisions captured
- Any fields that were left out due to insufficient evidence
- Any validation warnings (if validator was available)

## Common Pitfalls

These are fields where the schema types are non-obvious and easy to get wrong.
Read `references/tricky-fields.md` for the full list before assembling JSON.

Key gotchas:
- **version formats**: ALL versions must be three-part semver (`>=3.12.0` not `>=3.12`).
  The `versionRange` regex requires `\d+\.\d+\.\d+` in all positions.
- **deployment.tools**: Array of `{name, version}` objects (namedToolExact), NOT strings.
  Example: `[{"name": "docker", "version": "27.0.0"}]`
- **dependencies.lock-files**: String enum `"required" | "optional" | "forbidden"`, NOT boolean.
- **dependencies.update-strategy**: Must be one of `"major-auto-merge" | "minor-auto-merge" | "patch-auto-merge" | "manual"`.
- **dependencies.version-pinning**: Object `{strategy, exact-for?}` where strategy is
  `"minor-range" | "patch-range" | "exact"`, NOT a string.
- **runtime**: Must be `null` for languages without a separate runtime (Python, Go, Rust, Java).
  Only languages like TypeScript/JavaScript need `{name: "node", version: "..."}`.
- **owner.team**: Must be lowercase kebab-case matching `^[a-z0-9]+(-[a-z0-9]+)*$`.
  When extracting from CODEOWNERS, strip the `@org/` prefix and convert to kebab-case.

## Multi-Process Projects

When docker-compose defines multiple services from a single codebase (e.g., a FastAPI app
and a Celery worker sharing the same source directory), model them as a **single project
entry** with the primary process type (usually `service`). Add `agent-hints` to document
the secondary processes. Don't create separate project entries for processes that share
a manifest, path, and version.

## Important Rules

- **Never invent values.** If you can't infer a field from the codebase and it's optional, omit it.
  If it's required, ask the user.
- **Batch your questions.** Don't ask one field at a time. Collect all unknowns and ask once.
- **Prefer technology-stack-overrides** over full technology-stack at the project level when
  the project mostly matches the global default.
- **Use the schema's enum values exactly.** Don't improvise enum entries — the schema is strict.
- **Set schema-version to "0.1.0"** as required by the schema `const` constraint.
- **Respect additionalProperties: false.** Don't add fields not in the schema.
- **Cross-reference rules matter.** Unique project names, unique ports, DAG dependencies,
  and environment-override key validity must all be correct.
- **Infer security tools from CI steps**, not just config files. A GitHub Actions step
  using `snyk/actions/node@master` means dependency-scanning is Snyk. A `gitleaks` pre-commit
  hook means secret-detection is Gitleaks. Parse CI workflows and pre-commit configs carefully.
