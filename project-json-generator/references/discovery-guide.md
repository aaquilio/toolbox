# Discovery Guide — File-to-Field Mapping

This reference tells you which files to examine and what schema fields they inform.
Use it during Phase 1 (Discovery) and Phase 2 (Inference).

## Table of Contents

- [Language & Technology Stack](#language--technology-stack)
- [Monorepo & Workspace Detection](#monorepo--workspace-detection)
- [CI/CD](#cicd)
- [Testing](#testing)
- [Code Quality](#code-quality)
- [Security](#security)
- [Observability](#observability)
- [Service Communication](#service-communication)
- [Release & Versioning](#release--versioning)
- [Dependencies](#dependencies)
- [Deployment](#deployment)
- [API](#api)
- [Infrastructure & Backing Services](#infrastructure--backing-services)
- [Project-Level Fields](#project-level-fields)
- [Owner Inference](#owner-inference)

---

## Language & Technology Stack

**Schema path:** `global.default-technology-stack`, `projects[].technology-stack`

| File | Fields Informed |
|---|---|
| `package.json` | language=typescript/javascript, version (from engines.node), runtime (node), package-manager (check for packageManager field, or presence of pnpm-lock/yarn.lock/package-lock), frameworks (from dependencies — express, nestjs, next, react, etc.) |
| `tsconfig.json` | Confirms TypeScript; check `target` and `module` for version hints |
| `pyproject.toml` | language=python, version (from requires-python, **must be three-part**: `>=3.12.0` not `>=3.12`), package-manager (poetry if build-system uses poetry-core, hatch if hatchling, pdm if pdm-backend, pip if setuptools or no build tool), runtime=**null**, frameworks (from dependencies — fastapi, django, flask, celery, etc.) |
| `setup.py` / `setup.cfg` | Same as pyproject.toml, older Python projects. package-manager={name: "pip"} |
| `go.mod` | language=go, version (from go directive, **three-part**: `>=1.22.0`), runtime=**null**, package-manager={name: "go-modules", version: <go version>} |
| `Cargo.toml` | language=rust, version (from rust-version or edition), package-manager={name: "cargo"} |
| `pom.xml` | language=java, version (from maven.compiler.source/target), package-manager={name: "maven"} |
| `build.gradle` / `build.gradle.kts` | language=java/kotlin, package-manager={name: "gradle"} |
| `Gemfile` | language=ruby, runtime={name: "ruby"}, package-manager={name: "bundler"} |
| `.nvmrc` / `.node-version` / `.tool-versions` | Refine version for Node.js projects |
| `.python-version` | Refine version for Python projects |

**Framework detection (Node/TS):** Check `dependencies` and `devDependencies` in package.json:
- `express` → {name: "express", version: <from package.json>}
- `@nestjs/core` → {name: "nestjs", version: <from package.json>}
- `next` → {name: "nextjs", version: <from package.json>}
- `react` → {name: "react", version: <from package.json>}
- `fastify` → {name: "fastify", version: <from package.json>}
- `hono` → {name: "hono", version: <from package.json>}

**Framework detection (Python):** Check `[project.dependencies]` or `[tool.poetry.dependencies]`:
- `fastapi` → {name: "fastapi", version: ...}
- `django` → {name: "django", version: ...}
- `flask` → {name: "flask", version: ...}

---

## Monorepo & Workspace Detection

**Schema path:** `metadata.type`

| File | Signal |
|---|---|
| `pnpm-workspace.yaml` | monorepo, pnpm workspaces — parse `packages` array for member paths |
| `package.json` → `workspaces` | monorepo, npm/yarn workspaces |
| `turbo.json` | monorepo (Turborepo) |
| `nx.json` | monorepo (Nx) |
| `lerna.json` | monorepo (Lerna) |
| `Cargo.toml` → `[workspace]` | monorepo (Rust workspace) |
| `go.work` | monorepo (Go workspace) |

If none found → `metadata.type = "standalone"`, and create a single entry in `projects[]`.

---

## CI/CD

**Schema path:** `global.ci-cd`

| File | Fields Informed |
|---|---|
| `.github/workflows/*.yml` | platform="github-actions", parse jobs for required-checks, look for branch protection in on.pull_request |
| `.gitlab-ci.yml` | platform="gitlab-ci", parse stages and rules |
| `Jenkinsfile` | platform="jenkins" |
| `.circleci/config.yml` | platform="circleci" |
| `azure-pipelines.yml` | platform="azure-devops" |
| `.buildkite/pipeline.yml` | platform="buildkite" |
| `bitbucket-pipelines.yml` | platform="bitbucket-pipelines" |

**required-checks:** Parse CI workflow files for job names / stage names that run on PRs.
Common patterns: `lint`, `test`, `typecheck`, `build`, `security-scan`.

**branch-protection:** Look for branch protection rules in CI config or infer from
workflow triggers (e.g., `on: pull_request` with `branches: [main]`). Default to
reasonable values if CI config suggests PR-based workflow:
`{ "required-reviews": 1, "require-passing-checks": true, "no-force-push": true }`.
But only include if there's evidence — otherwise ask.

---

## Testing

**Schema path:** `global.testing`

| File | Fields Informed |
|---|---|
| `jest.config.*` | runner="jest" |
| `vitest.config.*` | runner="vitest" |
| `pytest.ini` / `pyproject.toml [tool.pytest]` / `setup.cfg [tool:pytest]` | runner="pytest" |
| `.mocharc.*` | runner="mocha" |
| `karma.conf.*` | runner="karma" |
| `package.json` scripts | Check `test` script for runner hints |
| `codecov.yml` / `.nycrc` / `jest --coverage` flags | coverage targets |

**strategy:** Hard to infer — default to omitting unless test file naming conventions
give a hint (e.g., `*.spec.ts` is common with BDD/TDD, `*_test.go` is standard Go).
Ask the user if no signal.

**coverage:** Look for coverage configuration. Map to schema entries like
`{ "type": "unit", "target": 80 }`. If exact targets aren't found, ask.

---

## Code Quality

**Schema path:** `global.code-quality`

| File | Fields Informed |
|---|---|
| `.eslintrc*` / `eslint.config.*` / `biome.json` | linter (eslint or biome), requirements includes "linter" |
| `.prettierrc*` / `biome.json` | formatter (prettier or biome), requirements includes "formatter" |
| `tsconfig.json` (strict mode) | typechecker="tsc", requirements includes "typechecker" |
| `mypy.ini` / `pyproject.toml [tool.mypy]` | typechecker="mypy" |
| `ruff.toml` / `pyproject.toml [tool.ruff]` | linter="ruff" and/or formatter="ruff" |
| `.pre-commit-config.yaml` / husky config | pre-commit=true |

---

## Security

**Schema path:** `global.security`

| File | Fields Informed |
|---|---|
| `.snyk` | dependency-scanning: {name: "snyk"} |
| `.semgreprc*` / `.semgrep.yml` | sast: {name: "semgrep", config-path: ...} |
| `.trivy.yaml` / `trivy.yaml` | container-scanning: {name: "trivy"} |
| `.gitleaks.toml` | secret-detection: {name: "gitleaks"} |
| CI workflow steps referencing security tools | Parse action names for tool identification |

If no security tooling is found, this is still a required global section. Ask the user
what they use, or note that they may need to set these up.

---

## Observability

**Schema path:** `global.observability`

| File/Dependency | Fields Informed |
|---|---|
| `@opentelemetry/*` dependencies | tracing and metrics provider/protocol hints |
| `pino` / `winston` / `bunyan` deps | logging.format (pino defaults to structured-json) |
| `structlog` / `python-json-logger` | logging.format="structured-json" |
| `docker-compose*.yml` services | Look for jaeger, zipkin, grafana, prometheus containers |
| `prometheus.yml` | metrics.provider="prometheus" |
| `otel-collector-config.yaml` | tracing/metrics protocol and provider |

---

## Service Communication

**Schema path:** `global.service-communication`

| Signal | Fields Informed |
|---|---|
| REST routes / Express/Fastify handlers | internal-sync="http-rest" |
| `@grpc/*` or protobuf files | internal-sync="grpc" |
| GraphQL schema files or `@apollo/*` deps | internal-sync="graphql" |
| `kafkajs` / `@nestjs/microservices` kafka | internal-async-transport: {protocol: "event-driven", broker: "kafka"} |
| `amqplib` / `amqp-connection-manager` | internal-async-transport: {protocol: "message-queue", broker: "rabbitmq"} |
| `@aws-sdk/client-sqs` | internal-async-transport: {broker: "sqs"} |
| `bullmq` / `bull` with Redis | internal-async-transport: {broker: "redis-streams"} |

---

## Release & Versioning

**Schema path:** `global.release`

| File | Fields Informed |
|---|---|
| `.releaserc*` / `release.config.*` | Semantic release → versioning="semver", changelog="conventional-commits" |
| `CHANGELOG.md` format | changelog format hint |
| `lerna.json` version field | versioning strategy |
| `.changeset/config.json` | Changesets → versioning="semver" |
| Git tags pattern | tagging convention |

---

## Dependencies

**Schema path:** `global.dependencies`

| Signal | Fields Informed |
|---|---|
| `package-lock.json` / `pnpm-lock.yaml` / `yarn.lock` | lock-files=true |
| `renovate.json` / `.github/renovate.json` | update-strategy="automated" |
| `dependabot.yml` | update-strategy="automated" |
| `package.json` dependency version prefixes | version-pinning: `^` = "range", exact = "exact" |
| LICENSE file or package.json license field | Hint for allowed-licenses (ask user to confirm) |

---

## Deployment

**Schema path:** `global.deployment`

| File | Fields Informed |
|---|---|
| `Dockerfile` / `docker-compose*.yml` | tools includes "docker" |
| `terraform/` directory / `*.tf` files | tools includes "terraform" |
| `pulumi/` or `Pulumi.yaml` | tools includes "pulumi" |
| `k8s/` / `kubernetes/` / `helm/` directories | tools includes "kubernetes" and/or "helm" |
| `serverless.yml` | tools includes "serverless-framework" |
| `cdk.json` / `cdk/` directory | tools includes "aws-cdk" |

---

## API

**Schema path:** `global.api`

| File | Fields Informed |
|---|---|
| `openapi*.yaml` / `openapi*.json` / `swagger.*` | style="rest", documentation="openapi-3.1" (check version) |
| GraphQL schema files (`.graphql`) | style="graphql", documentation="graphql-schema" |
| `.proto` files | style="grpc" |
| `asyncapi.yaml` | documentation="asyncapi" |
| Auth middleware / passport config | authentication methods |
| Rate limiter middleware (express-rate-limit, etc.) | rate-limiting config |

**versioning:** Look for `/api/v1/` patterns in routes → "url-prefix". Header-based
versioning is harder to detect — ask if unclear.

---

## Infrastructure & Backing Services

**Schema path:** `global.infrastructure`, `projects[].infrastructure`

| Signal | Fields Informed |
|---|---|
| `docker-compose*.yml` services | backing-services entries (postgres, redis, mongo, elasticsearch, etc.) |
| Database migration directories (prisma/, drizzle/, knex/, alembic/, migrations/) | relational-db type and provider hint |
| `prisma/schema.prisma` datasource | provider (postgresql, mysql, sqlite) |
| Redis client deps (`ioredis`, `redis`) | cache or key-value-store |
| S3/MinIO configuration | object-storage |
| Elasticsearch/OpenSearch client deps | search-engine |

---

## Project-Level Fields

For each project in a monorepo (or the single project in standalone):

| Field | Source |
|---|---|
| `name` | package.json `name`, directory name |
| `path` | Relative path from repo root (e.g., `packages/api`, `apps/web`, or `.` for standalone) |
| `type` | Infer: has HTTP routes → `service` or `app`; React/Vue/Angular → `frontend`; no server → `library`; CLI entry point → `cli`; queue consumer → `worker` |
| `description` | package.json `description`, README first paragraph |
| `version` | package.json `version`, Cargo.toml version, pyproject.toml version |
| `lifecycle` | Default `"active"`. Mark `"deprecated"` if README says DEPRECATED or package.json has `deprecated` field |
| `port` | Dockerfile `EXPOSE`, docker-compose `ports`, server listen() calls, `.env` PORT variable |
| `depends` | Workspace dependency references (e.g., `"@myorg/shared": "workspace:*"`), docker-compose `depends_on` |
| `consumes` | HTTP client calls to other internal services, message queue consumer/producer patterns |

---

## Owner Inference

**Schema path:** `projects[].owner`

| File | Fields Informed |
|---|---|
| `CODEOWNERS` | Map path patterns to team slugs |
| `.github/CODEOWNERS` | Same, GitHub-specific location |
| `package.json` author/contributors | Hint for team (but usually individual, not team slug) |

`owner.team` is **required** and follows the pattern `^[a-z0-9]+(-[a-z0-9]+)*$` (lowercase kebab-case).
If CODEOWNERS doesn't provide a clear mapping, **ask the user**.

`owner.contact` and `owner.escalation-channel` are optional — only include if evidence exists.
