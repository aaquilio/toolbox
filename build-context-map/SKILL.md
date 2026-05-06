---
name: build-context-map
description: >
  Builds and maintains a structured, hierarchical .context/ directory that gives coding agents
  a comprehensive, token-efficient understanding of one or more repos — equivalent to the
  mental model of a senior principal engineer who knows the codebase inside and out.

  Use this skill whenever the user asks to:
  - "map", "analyze", "index", or "document" a codebase or repo
  - "build context" or "generate context" for a project
  - "update the context map" after code changes
  - understand an unfamiliar codebase before working in it
  - set up a coding agent to work in a repo it hasn't seen before
  - run a .context refresh, re-scan, or re-analysis

  Trigger even for casual phrasings like "can you get familiar with this repo", "learn the
  codebase", "understand how this system works", or "prep context before we start coding".
---

# Context Cartographer

Builds and maintains a `.context/` directory tree: a hierarchical, versioned knowledge base
of one or more repos. The output is engineered for coding-agent consumption — accurate,
structured, citation-backed, and token-efficient.

The skill prioritizes **depth and correctness over speed**. It is expected to be slow on
large repos. It compensates by producing artifacts that can be loaded by hundreds of
downstream coding sessions without re-analysis.

---

---

## Skill Bundle

This skill ships with two non-prose resources that the orchestrator MUST use:

- **`scripts/validate.py`** — stdlib-only Python validator. Run as the final step of
  Phase 5 (see Phase 5e). Exit code 0 = pass, 1 = findings present, 2 = invocation
  error.
- **`resources/schema.json`** — JSON Schema reference for `.context/` artifact
  front-matter. Authoritative source of required fields and value formats. The
  validator and analyzers MUST conform to it; if it disagrees with prose in this
  SKILL.md, the schema wins.

The orchestrator may pass the schema path to analyzers that need to confirm exact
front-matter shape.

---

## Output Structure

```
.context/
├── map.md                          ← System-of-systems overview + repo index
├── $REPO/
│   ├── context.md                  ← Repo analysis + subsystem index
│   └── $SUBSYSTEM/
│       └── context.md              ← Deep-dive: APIs, patterns, agent rules
├── .handoff/                       ← Transient inter-worker messages (gitignored)
└── .scratch/                       ← Transient orchestrator notes (gitignored)
```

`.handoff/` and `.scratch/` are working memory for the orchestrator and workers. They are
created at the start of a run and may be deleted after a successful run completes. The
orchestrator MUST add these paths to `.context/.gitignore` on first creation.

### File header

Every `.md` file in `.context/` (except `.gitignore`) starts with this YAML front-matter:

```yaml
---
file: .context/$RELATIVE_PATH
scope: <repo path or repo/subsystem path this file describes>
created: YYYY-MM-DD
updated: YYYY-MM-DD
commit: <git commit hash at time of last update>
origin: <git remote origin URL, or "none">
analyzer_version: <semver of this skill at time of write>
review_depth: none | per_scope | full
confidence: HIGH | MEDIUM | LOW
---
```

For `map.md`, replace `origin` with an `origins:` sequence listing every repo:

```yaml
origins:
  - payments-service: https://github.com/acme/payments-service
  - frontend: https://github.com/acme/frontend
  - acme-proto: https://github.com/acme/acme-proto
```

Capture origin with `git -C $REPO remote get-url origin`. If no remote is configured,
set `origin: none`.

### Confidence levels

- **HIGH** — directly verifiable from source files, configs, or git history. Every HIGH
  claim MUST carry an inline citation: `` `path/to/file.ext:LINE` `` or
  `` `path/to/file.ext:LINE-LINE` ``.
- **MEDIUM** — inferred from patterns, naming, or structure. Plausible but not confirmed
  by explicit code. No inline citation required, but a "based on" note is recommended.
- **LOW** — best-effort with limited signals. Downstream agents should verify before
  relying on it.

The default for any claim is MEDIUM. HIGH must be earned with a citation. LOW must be
declared explicitly.

### Section confidence

Each section within a file carries an HTML-comment confidence annotation:

```markdown
## Section Title
<!-- confidence: HIGH -->
...content...
```

The section confidence is the floor of all claim confidences inside it. A section
containing any LOW claim is at most LOW.

---

## Execution Model

This skill defines a **role contract**, not a runtime. Any harness that implements the
contract works. The reference implementation is Claude Code with the Task tool.

### Three roles, hard-isolated

| Role | Sees | Produces | Constraint |
|------|------|----------|------------|
| **Orchestrator** | Plan, worker return values, written files | Plan, dispatched scopes, final assembly | Never reads source itself |
| **Analyzer** | Source files in its assigned scope | One `context.md` for its scope + structured handoff | Isolated context per invocation; sees no other analyzer's work |
| **Reviewer** | The written `context.md` + the source it describes | Structured findings list | Never sees analyzer reasoning or other reviewers' findings |

Isolation is the point. A reviewer that has seen the analyzer's reasoning anchors on it
and rubber-stamps the artifact. A reviewer with only the artifact and the source must
re-derive each claim to verify it. That is the bias break.

### The Analyzer Contract

An analyzer is **any agent invocation** that satisfies this contract:

**Input:**
- `scope_path` — absolute path to the directory it must analyze
- `scope_kind` — one of `repo`, `subsystem`, `database`, `cloud`, `cross_repo`
- `parent_handoffs` — list of paths to relevant `.handoff/*.md` files from prior analyzers (may be empty)
- `output_path` — where to write its `context.md`
- `handoff_path` — where to write its handoff for downstream consumers
- `exclusions` — combined list of patterns to skip (see Exclusions section)

**Output:**
- A `context.md` written to `output_path`, conforming to the file header and content
  rules for its `scope_kind`.
- A `handoff.md` written to `handoff_path` containing only:
  - **Boundary surfaces**: APIs, types, schemas, events this scope exposes that other
    scopes may consume
  - **Dependencies asserted**: things this scope expects to exist elsewhere (with the
    file:line where the assumption is made)
  - **Open questions**: anything the analyzer could not resolve and flagged LOW
  - **Scale signals**: file count, total LOC analyzed, any sub-scopes the analyzer
    recommends spawning recursively (see Scope Decomposition)

**Return value to orchestrator** (kept small to preserve orchestrator context):
- `output_path`, `handoff_path`
- File counts: analyzed, skipped, excluded
- Recommended sub-scopes (if any)
- Any errors or partial-completion flags

The analyzer MUST NOT return prose summaries. The `context.md` is the artifact;
everything else is metadata.

### The Reviewer Contract

A reviewer is invoked per artifact. There are three reviewer types (see Phase 5).

**Input:**
- `artifact_path` — the `context.md` under review
- `scope_path` — the source directory the artifact claims to describe
- `checklist` — the validation checklist for this reviewer type
- `exclusions` — same exclusions used by the analyzer

**Output:**
- A `review.md` written to `.context/.handoff/reviews/$SCOPE_ID.review.md` containing a
  structured findings list (see Phase 5 for format).

The reviewer MUST NOT see: analyzer scratch notes, handoff files from other analyzers,
or other reviewers' findings.

### Configurable review depth

The orchestrator accepts a `review_depth` parameter:

- **`none`** — no review pass. Fast but unsafe. Allowed only for re-runs of unchanged
  content during Smart Update.
- **`per_scope`** — every written `context.md` gets a per-scope reviewer.
- **`full`** (default) — per-scope reviewers, plus a cross-repo consistency reviewer,
  plus a rules reviewer.

Default for first build: `full`. Default for Smart Update: `per_scope` on changed scopes,
`none` on unchanged.

---

## Phase 0 — Detect Mode

Before doing anything else:

1. Check for `.context/map.md`.
2. If absent → run **Full Build** (Phases 1 → 5).
3. If present → run **Smart Update** (Phase U).

The orchestrator records the chosen mode in its plan and announces it to the user.

---

## Phase 1 — Discovery (Orchestrator)

The orchestrator performs Phase 1 directly. It is shallow enough to fit in one context.

### 1a. Enumerate repos

- Find all `.git/` directories under the target. Each is a repo root.
- Note repo names, top-level structure, monorepo signals (`packages/`, `services/`,
  `apps/`, `libs/`, `pnpm-workspace.yaml`, `Cargo.toml` workspace, `go.work`, etc.).

### 1b. Surface signals (per repo)

Read these before any source code:

| Signal | Where to look |
|--------|---------------|
| Purpose / domain | `README.md`, `CONTRIBUTING.md`, repo name |
| Languages | File extensions, `package.json`, `Cargo.toml`, `go.mod`, `pyproject.toml`, `pom.xml`, `build.gradle`, `.tool-versions` |
| Runtime / platform | `Dockerfile`, `docker-compose.yml`, `.github/workflows/`, `Makefile`, `justfile` |
| Entry points | `main.*`, `cmd/`, `src/index.*`, `app.*`, `server.*` |
| Dependency manifests | Lock files, manifest files |
| Test layout | `tests/`, `spec/`, `__tests__/`, framework configs |
| Config / env | `.env.example`, `config/`, `settings.*` |
| Existing docs | `docs/`, `ADRs/`, `architecture/` |
| Git history | `git log --oneline -50`, recent PR titles |

### 1c. Cross-repo signals

- Shared package names imported across repos
- Shared proto/schema/contract files
- Docker Compose or Kubernetes manifests wiring services
- Monorepo workspace declarations
- CI/CD pipelines that deploy multiple repos together

Record a preliminary dependency graph. It will be refined in Phase 3.

### 1d. Build the analyzer plan

The orchestrator decomposes each repo into analyzer scopes (Scope Decomposition below)
and writes the plan to `.context/.scratch/plan.md`. The plan lists every scope to be
dispatched, in dispatch order, with dependencies between scopes.

---

## Scope Decomposition

The orchestrator turns "the repo" into a deterministic-ish set of analyzer scopes. The
goal is that two runs against the same repo state produce the same scope list.

### Algorithm

1. Start with the repo root as a candidate scope.
2. Apply the **Decomposition Triggers** below. If any fires, replace the candidate with
   its child directories as candidates and recurse.
3. Stop when no trigger fires. The remaining candidates are the analyzer scopes.

### Decomposition triggers

A scope must be decomposed if any of the following hold:

| Trigger | Threshold |
|---------|-----------|
| File count | More than 150 source files (after exclusions) |
| Total source LOC | More than 30,000 lines (after exclusions) |
| Distinct top-level concerns | 4+ child directories that each independently match a "subsystem" pattern (e.g. `api/`, `worker/`, `cli/`, `migrations/`) |
| Monorepo workspace | The directory is declared as a workspace member (`packages/*`, `services/*`, etc.) |
| Domain marker | Contains a `README.md` that names it as a distinct subsystem, or a top-level concept directory like `domain/`, `internal/`, `pkg/` with multiple children |

### Reserved scopes

Regardless of decomposition, the orchestrator creates dedicated scopes when these are
detected anywhere in a repo:

- **`database/`** — if any persistent store is detected (see Phase 2 Database Deep Dive).
  Scope covers all migrations, schema files, and repository/DAO layers.
- **`cloud/`** — if any cloud SDK or IaC file is detected. Scope covers all cloud
  integrations across the repo.

These reserved scopes may overlap with subsystem scopes. That is acceptable; the analyzer
for each writes about its own concern only.

### Recursion

If an analyzer reports in its handoff that its scope is itself too large (file count or
LOC over threshold), the orchestrator decomposes it further and re-dispatches. Recursion
depth is capped at 4 levels to prevent runaway.

### Recording the plan

The plan written to `.context/.scratch/plan.md` lists every scope with its
`scope_path`, `scope_kind`, file count estimate, and dispatch dependencies. The plan is
the orchestrator's working memory and is overwritten on every run.

---

## Exclusions

The analyzer skips files matching the exclusion list. The orchestrator builds the list
from three sources, in order:

1. **Built-in defaults** (always applied):
   - VCS: `.git/`, `.hg/`, `.svn/`
   - Dependencies: `node_modules/`, `vendor/`, `bower_components/`
   - Build output: `dist/`, `build/`, `out/`, `target/`, `bin/`, `obj/`, `__pycache__/`, `.next/`, `.nuxt/`, `.svelte-kit/`
   - Generated: `*.pb.go`, `*_pb2.py`, `*.generated.*`, `*.gen.go`
   - Minified: `*.min.js`, `*.min.css`
   - Lockfiles (already captured in Phase 1b): `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `Cargo.lock`, `poetry.lock`, `Gemfile.lock`, `go.sum`
   - Binary assets: images, fonts, audio, video, archives
   - Coverage / cache: `coverage/`, `.nyc_output/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`
   - IDE: `.idea/`, `.vscode/` (unless it contains team-shared workspace config)

2. **`.gitignore` patterns** from each repo (treat anything gitignored as excludable
   unless it matches a re-include pattern below).

3. **`.contextignore`** at the repo root, if present. Same syntax as `.gitignore`. Lines
   starting with `!` re-include. This is the user's escape hatch.

The analyzer reports excluded file counts in its handoff. If exclusions appear to be
hiding meaningful source (e.g. a `dist/` directory is the only place the user keeps
hand-written code), the analyzer flags it in the handoff and the orchestrator surfaces
it in the final report.

---

## Phase 2 — Deep Source Analysis (Analyzer, per scope)

Each analyzer is invoked once per scope per the Analyzer Contract above. The analyzer
performs a full read of every non-excluded source file in its scope.

The analyzer extracts the following. Each subsection has explicit confidence rules.

### Architecture
- Architectural style (layered, hexagonal, event-driven, microservices, monolith, CQRS, etc.)
- Directory organization and rationale
- Module/package boundaries and responsibilities
- Dependency direction rules

HIGH only if a structural marker confirms it (a layout convention, an explicit
`internal/` boundary, an enforced lint rule). Otherwise MEDIUM.

### Design Patterns
- Patterns in active use (repository, factory, observer, middleware chain, decorator, saga, etc.)
- Where each pattern appears (with `file:line` for HIGH)
- Anti-patterns or notable deviations

A pattern claim is HIGH only with at least two distinct citations showing the pattern
applied consistently. A single instance is MEDIUM ("appears in one place").

### Data Model & Database Deep Dive

Triggered by ORM imports, raw SQL, migration files, connection config, schema files.

#### Schema (HIGH-eligible)
For every table/collection: name, columns/fields with type, nullable, default,
constraints, indexes, foreign keys, ON DELETE/UPDATE behavior, CHECK constraints,
triggers, enums. Cite the migration or schema file for each.

#### Queries (MEDIUM by default)
- Statically discoverable queries: SQL string literals, ORM call chains, query builder
  expressions. List with `file:line`.
- **Dynamic query construction sites**: any place queries are built from concatenation,
  templating, or runtime composition. List the site, mark as "dynamic — content not
  statically determinable."
- N+1 risks: loop-issued queries or unguarded eager/lazy loads. Cite each.
- Transactions: where used, what they wrap, isolation level if specified.

The "all queries" claim is MEDIUM at best in any codebase with dynamic SQL. Be honest
about this in the file.

#### ORM / Query Builder (HIGH-eligible)
Which ORM, how it is used (raw SQL vs. query builder vs. full ORM), model definitions
and their schema mapping, migration tool and convention, whether migrations are
reversible.

#### Migration History (HIGH-eligible)
Sequence and purpose of migrations from oldest to newest. Notable schema evolutions.
Whether any migration was modified after initial commit (check via
`git log -- $MIGRATION_FILE` and flag as HIGH risk if so).

#### Performance Notes (MEDIUM)
Indexed vs. unindexed columns used in WHERE/ORDER, large-table signals, EXPLAIN
annotations, performance comments.

**Database inventory table** (in repo `context.md`):

| DB | Type | Purpose | ORM/Driver | Schema Source |
|----|------|---------|-----------|---------------|
| `acme_db` | PostgreSQL 15 | payments ledger | pgx v5 (raw SQL) | `migrations/` |

#### Domain Entities
Core domain objects and relationships. Data flow.

### APIs & Interfaces
- Public APIs: REST, gRPC, GraphQL, WebSocket, CLI — endpoints, methods, schemas
- Internal interfaces: key abstractions, contracts between layers
- Pre/postconditions for non-trivial functions
- Error handling conventions

HIGH for anything declared in a schema file (OpenAPI, `.proto`, GraphQL SDL) with the
schema cited. MEDIUM for hand-rolled HTTP routes inferred from handler registrations.

### Infrastructure & Runtime
- Deployment and run model
- Key environment variables and effects
- Feature flags, configuration layers
- Observability: logging, metrics, tracing

### Cloud Services

Detection: import statements, SDK instantiation, env var names, IAM references, IaC
files (`.tf`, CDK, SAM, Pulumi, `serverless.yml`, CloudFormation), config files.

| Provider | SDK signals | Service signals |
|----------|------------|-----------------|
| AWS | `aws-sdk-go`, `boto3`, `@aws-sdk/*`, `Aws::` | S3, SQS, SNS, DynamoDB, RDS, Lambda, ECS, ECR, Secrets Manager, Parameter Store, CloudWatch, Kinesis, EventBridge, SES, Cognito |
| GCP | `google-cloud-*`, `cloud.google.com/go/*` | Cloud Storage, Pub/Sub, Firestore, BigQuery, Cloud Run, GKE, Secret Manager, Cloud Tasks |
| Azure | `azure-sdk-for-*`, `Azure::` | Blob Storage, Service Bus, Cosmos DB, Azure Functions, AKS, Key Vault |
| Generic | HTTP calls to `*.amazonaws.com`, `*.googleapis.com`, `*.azure.com` | (record host and pattern) |

Per detected service: name, provider, purpose, access pattern, configuration env vars,
data shape, error handling (retries, DLQ, fallback), IAM/permissions notes.

**Cloud services inventory table**:

| Provider | Service | Purpose | Config Key(s) | Access Pattern |
|----------|---------|---------|---------------|----------------|
| AWS | S3 | Profile image storage | `AWS_S3_BUCKET`, `AWS_REGION` | SDK PutObject/GetObject |
| AWS | SQS | Order processing queue | `SQS_QUEUE_URL` | SDK SendMessage, polling consumer |

### Implementation Intricacies
- Non-obvious logic that would surprise a new engineer
- Performance-sensitive paths
- Known workarounds, TODOs, tech debt signals
- Concurrency model

### Handoff (required output)

The analyzer writes a handoff at `handoff_path` with these sections:

```markdown
# Handoff: $SCOPE_ID

## Boundary surfaces exposed
- <surface>: <type> at <file:line>

## Dependencies asserted on other scopes
- <claim about other scope> — assumed at <file:line>

## Open questions
- <question> — relevant files: <list>

## Scale signals
- files_analyzed: N
- files_excluded: N
- loc_total: N
- recommended_sub_scopes: [<path>, ...] (empty if none)
```

The orchestrator uses handoffs to (a) wire cross-scope references in `map.md`,
(b) detect contradictions in Phase 3, (c) decide whether to recurse.

---

## Phase 3 — Cross-Repo Synthesis (Orchestrator)

After all per-repo analyzers complete, the orchestrator synthesizes cross-repo
understanding from handoffs only (it does not re-read source).

- **Service boundaries**: what each repo owns, what it does not
- **API contracts**: where repos communicate, schemas, versioning
- **Shared libraries**: what is shared, coupling implications
- **Data ownership**: which repo owns which data; flag any conflicts (two repos
  claiming the same table is a HIGH-priority finding for the cross-repo reviewer)
- **Failure modes**: cascading failures across repos
- **Deployment topology**: runtime relationships

Output is held in `.context/.scratch/cross_repo.md` until Phase 4c writes `map.md`.

---

## Phase 4 — Write `.context/` Files

Files are written **bottom-up**: subsystem files first, then repo files, then `map.md`.
This ordering exists so each layer can reference and summarize the layer below.

### 4a. Subsystem files: `.context/$REPO/$SUBSYSTEM/context.md`

Written by the subsystem analyzer. Contains:

- File header (see Output Structure)
- Subsystem purpose and bounded responsibility
- Key files with paths and roles
- Internal APIs and interfaces with pre/postconditions
- Design patterns used and citations
- Implementation intricacies and gotchas
- Agent coding rules (see Agent Rules below)
- Per-section confidence annotations

### 4b. Repo files: `.context/$REPO/context.md`

Written by a repo-level analyzer that consumes subsystem handoffs (not subsystem files).
Contains:

- File header
- Repo overview: purpose, domain, maturity
- Technology stack
- Architecture style and rationale
- Directory map with responsibility annotations
- Database inventory table
- Cloud services inventory table
- Public API surface summary
- Key design patterns (cross-subsystem)
- Agent coding rules for this repo
- **Subsystem index**: for each subsystem `context.md`, one sentence describing what it
  covers and when an agent should load it
- Per-section confidence annotations

### 4c. `.context/map.md`

Written by the orchestrator from cross-repo synthesis and repo handoffs. Contains:

- File header (with `origins:` sequence)
- System-of-systems overview: what the whole thing does, who uses it, what problem it solves
- Cross-repo dependency graph (text or ASCII)
- Service boundary summary: one paragraph per repo
- API contract registry: known cross-repo contracts and their location
- System-wide database inventory
- System-wide cloud services inventory
- **Repo index**: 2–3 sentences per repo guiding when to load it
- System-wide agent rules
- Per-section confidence annotations

---

## Agent Rules Format

Every `context.md` includes an `## Agent Rules` section. Format:

```markdown
## Agent Rules
<!-- confidence: HIGH -->

- **ALWAYS** use the repository pattern for data access; never query the DB directly from handlers — see `internal/store/store.go:1-40`
- **NEVER** add business logic to `cmd/` — it belongs in `internal/service/` (convention enforced by `cmd/main.go:12-30`)
- **PREFER** returning errors over panicking; panics are reserved for unrecoverable startup failures — see `pkg/errors/errors.go:55`
- **CHECK** `pkg/middleware/auth.go` before adding any new authenticated route
- **NOTE** all database migrations live in `migrations/`; never modify an existing migration file
```

Rules MUST be derived from observed patterns with at least one citation. Rules without
citations are removed by the rules reviewer (Phase 5c).

---

## Phase 5 — Review (three reviewer types)

The orchestrator dispatches reviewers after all `context.md` files are written. Each
reviewer is an isolated agent invocation per the Reviewer Contract above.

A reviewer NEVER sees: analyzer scratch notes, analyzer handoffs, the orchestrator's plan,
other reviewers' findings, or other `context.md` files outside its scope.

### 5a. Per-scope review (one per `context.md`)

**Inputs**: the artifact, the source it describes, the per-scope checklist.

**Checklist**:

1. **Citation integrity**: every `file:line` citation resolves. The cited line/range
   exists and contains content matching the claim.
2. **Confidence calibration**: every HIGH claim has a citation. Claims without citations
   are downgraded to MEDIUM. Claims contradicted by source are flagged.
3. **Path validity**: every file path mentioned in the artifact exists in the source.
4. **Coverage check**: a sample of source files in the scope (at least 10% or 20 files,
   whichever is larger) is spot-checked against the artifact. Files containing
   significant logic not reflected in the artifact are flagged as "missed coverage".
5. **Header completeness**: front-matter has all required fields, dates and commit are
   plausible.

**Output** (`review.md`):

```markdown
# Review: $SCOPE_ID
- artifact: <path>
- verdict: PASS | DOWNGRADE_REQUIRED | REWRITE_REQUIRED

## Findings
- [confidence_correction] <claim> — should be MEDIUM (no citation found at <claimed file:line>)
- [missing_coverage] <file> — contains significant logic not described in artifact
- [contradicted] <claim> — source at <file:line> says otherwise
- [broken_citation] <citation> — file does not exist / line out of range
- [header_issue] <field> missing or invalid
```

### 5b. Cross-repo consistency review (one per build)

**Inputs**: all repo-level `context.md` files plus `map.md`. No subsystem files.

**Checklist**:

1. **Data ownership conflicts**: two repos claiming the same table, queue, or topic.
2. **API contract mismatches**: repo A claims to call repo B's endpoint X, but repo B's
   API surface does not list X.
3. **Dependency direction conflicts**: A says it depends on B, B says it depends on A,
   neither acknowledges a cycle.
4. **Inventory consistency**: system-wide tables in `map.md` reconcile with per-repo
   tables.

**Output**: `cross_repo_review.md` with the same findings format as 5a, plus a
"reconciliation needed" list.

### 5c. Rules review (one per `context.md` that contains agent rules)

**Inputs**: the artifact's `## Agent Rules` section and the source it describes.

**Checklist**:

1. Each rule cites at least one source location, OR is supported by an observable
   pattern the reviewer can verify by reading the cited area.
2. Rules that contradict observed code are flagged.
3. Rules that are generic best-practice (not specific to this codebase) are flagged
   as "low value — applies anywhere".
4. Rules whose evidence is a single occurrence are downgraded to "PREFER" or "NOTE"
   from "ALWAYS"/"NEVER".

**Output**: `rules_review.md` with per-rule verdicts.

### 5d. Apply review findings

After reviewers complete, the orchestrator processes findings:

- **DOWNGRADE_REQUIRED**: orchestrator edits the artifact to apply confidence
  downgrades and removes/weakens unsupported rules. No re-dispatch needed.
- **REWRITE_REQUIRED**: orchestrator re-dispatches the analyzer with the findings
  attached as input. Capped at 2 rewrite cycles per scope.
- **Cross-repo findings**: orchestrator edits `map.md` and the affected repo files
  to reconcile, or flags the conflict explicitly with LOW confidence and a "human
  review needed" note.

### 5e. Structural validation (deterministic)

After review findings are applied, the orchestrator runs the bundled validator script:

```bash
python3 ${SKILL_DIR}/scripts/validate.py .context/ \
  --repo-root <repo1> [--repo-root <repo2> ...] \
  --json
```

The validator is stdlib-only Python and enforces these checks (see
`resources/schema.json` for the full reference schema):

- **Front-matter**: present, parseable, all required fields, no extras, valid types,
  enum values for `confidence` and `review_depth`, ISO dates, semver
  `analyzer_version`, valid commit hash format, valid origin URL.
- **Date order**: `updated >= created`.
- **Section confidence**: every heading is followed by a
  `<!-- confidence: HIGH|MEDIUM|LOW -->` annotation.
- **Citations**: every `` `path:line` `` or `` `path:line-line` `` resolves — file
  exists relative to the scope, line range within bounds.
- **HIGH requires citation**: every HIGH-confidence section contains at least one
  citation.
- **Path references**: backticked paths that look like source files exist on disk.
- **Index integrity**: every `$REPO/context.md` is named in `map.md`; every
  `$REPO/$SUBSYSTEM/context.md` is named in its parent `$REPO/context.md`.
- **No orphans**: no `.md` file under `.context/` (excluding `.scratch/` and
  `.handoff/`) is unreachable from `map.md`.
- **Commit verification**: the `commit` field resolves in the cited repo (skipped
  when `origin: none`).

The validator emits structured findings as JSON when `--json` is passed. Each
finding has a `category`, `file`, optional `line`, `message`, and optional `hint`.
Exit code is 0 on pass, 1 on findings present, 2 on invocation error.

### 5f. Auto-repair pass (one attempt)

If the validator returns non-zero, the orchestrator dispatches **one** repair
analyzer with these inputs:

- The full JSON findings list from the validator.
- The set of artifact files mentioned in the findings.
- Read access to the source tree.

The repair analyzer is given a narrow contract: fix only what the validator
flagged. It MUST NOT add new analysis, expand sections, or change unaffected
content. Permitted edits:

- Add/correct front-matter fields, including downgrading `confidence` when a
  citation cannot be added.
- Add missing `<!-- confidence: ... -->` annotations.
- Downgrade HIGH sections without citations to MEDIUM, OR add a citation if one
  can be derived from the source.
- Fix or remove broken `path:line` citations.
- Add missing index entries (subsystem in parent, repo in `map.md`).
- Move orphan files to `.context/.scratch/` or delete them after recording the
  decision in the run report.

After the repair pass, the orchestrator re-runs the validator. If validation
still fails, the orchestrator does **not** attempt a second repair. It reports
the remaining findings to the user and exits non-zero. This cap is intentional:
repeated repair loops indicate a structural problem the user must inspect.

The single retry is sufficient for mechanical fixes (missing fields, broken
citations from a recent edit) without risking a runaway repair-loop that masks
a real defect.

---

## Phase U — Smart Update

Run when `.context/` already exists.

### U1. Detect changes

```bash
LAST_COMMIT=$(grep '^commit:' .context/$REPO/context.md | awk '{print $2}')

# Changed, added, deleted, renamed files
git -C $REPO log --name-status --pretty=format: $LAST_COMMIT..HEAD | sort -u
```

For each repo, classify changes:
- `M` modified
- `A` added
- `D` deleted
- `R` renamed

### U2. Drift and orphan check

Before re-analyzing, the orchestrator scans existing `.context/` files for stale
references:

- **Orphaned context files**: a `.context/$REPO/$SUBSYSTEM/context.md` whose `scope`
  path no longer exists → mark for deletion.
- **Stale citations**: any `file:line` citation in an existing `context.md` that no
  longer resolves → mark the affected section for re-analysis.
- **Renames**: if a renamed file appears in a context file's citations, mark for
  re-analysis (paths must be updated).

Orphan deletions and rename-triggered re-analysis are part of the update plan.

### U3. Classify impact

For each changed file, determine:
- Which subsystem(s) it belongs to.
- Whether it affects cross-repo contracts (API/proto/schema/shared lib files) →
  cross-repo re-synthesis required.
- Whether it affects database shape (migration, schema, ORM model) → re-run database
  deep dive for the affected repo.
- Whether it affects cloud usage (new SDK call, new env var, IaC change) → re-run
  cloud analysis.

### U4. Detect new subsystems

If new top-level directories appeared that match Decomposition Triggers, the
orchestrator creates new subsystem scopes and dispatches analyzers for them. The
parent repo `context.md` and `map.md` indexes are updated accordingly.

### U5. Re-analyze

- **Changed scopes**: full re-analysis (Phase 2). Replace the existing `context.md`.
- **Unchanged scopes that depend on changed scopes**: ripple check. Read only the
  cross-scope interface files; update cross-references in their `context.md`. No full
  re-analysis.
- **Unchanged scopes with no dependency on changed scopes**: skip.

### U6. Review

Default `review_depth` for Smart Update is `per_scope` on changed scopes plus
cross-repo review if any cross-repo contract changed. `none` for untouched scopes.

### U7. Update headers

Bump `updated`, `commit`, and `analyzer_version` on every rewritten file. Do not bump
files that were not changed.

---

## Versioning

The skill itself is versioned (`analyzer_version` in headers). Individual context files
do not carry a separate version; the `commit` and `updated` fields are sufficient
identity. If the skill version changes between runs, the orchestrator notes it in the
final report and recommends a full rebuild if structural fields changed.

---

## Reporting

After a run, the orchestrator reports to the user:

- Mode (Full Build vs. Smart Update)
- Scopes analyzed, with file/LOC counts
- Files written, with paths
- Review depth used
- **Validator outcome**: pass, repaired-then-pass, or fail with remaining findings
- All LOW-confidence sections with a one-line reason each
- All findings the orchestrator could not auto-resolve (cross-repo conflicts, ambiguous
  source, exclusions that may have hidden meaningful code, validator findings the
  repair pass could not fix)
- Any rewrite cycles that hit the cap of 2
- Any orphan files moved to `.scratch/` or deleted by the repair pass
- Recommended next steps the user should review manually

The orchestrator does not claim the artifact is correct — it reports which checks the
artifact passed (review depth + validator). Correctness is established by use.

---

## Execution Notes

- **Bottom-up**: analyze before writing; write subsystems before repos before `map.md`.
- **Be exhaustive in analysis, disciplined in output**: read everything in scope, write
  only what's useful to a coding agent.
- **Avoid prose filler**: context files are reference documents, not essays. Use
  structure, lists, tables, headers.
- **Be specific**: "uses repository pattern" is less useful than "all DB access goes
  through `internal/store/` interfaces defined in `internal/store/store.go:1-40`".
- **Token efficiency**: the output will be loaded into agent context windows; prefer
  precision over completeness-for-its-own-sake.
- **Never fabricate**: if you cannot determine something from source, say so and mark
  LOW. Inventing patterns or rules poisons every downstream session.
- **Flag drift**: if existing `.context/` claims are no longer accurate, fix them and
  note the correction in the report.
- **Trust the contract, not the runtime**: any harness that satisfies the role contracts
  works. Claude Code with the Task tool is the reference; other harnesses are valid if
  they preserve isolation between roles.
