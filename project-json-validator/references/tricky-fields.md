# Tricky Fields Reference

Fields where the schema type is non-obvious or where agents commonly produce invalid values.
Consult this before assembling the JSON.

---

## Version Formats

The schema defines two version types. **Every version string must use three-part semver.**

### versionRange
Pattern: `^(\*|\d+(\.\d+)?\.x|[~^]\d+\.\d+\.\d+|>=\d+\.\d+\.\d+(\s*<\d+\.\d+\.\d+)?)$`

Valid examples:
- `"*"` — any version
- `"5.x"` or `"3.12.x"` — minor-range shorthand
- `"^5.3.0"` — caret (compatible with)
- `"~5.3.0"` — tilde (patch-level)
- `">=3.12.0"` — lower-bound
- `">=3.12.0 <4.0.0"` — explicit range

**Invalid examples:**
- `">=3.12"` — missing patch version ❌
- `"5.3"` — not a valid pattern ❌
- `"latest"` — not supported ❌
- `"^5.3"` — caret requires three parts ❌

### versionExact
Pattern: `^\d+\.\d+\.\d+$`

Valid: `"27.0.0"`, `"1.30.0"`, `"0.5.0"`
Invalid: `"27.0"`, `"latest"`, `"^1.0.0"` (no range operators)

---

## technology-stack

```json
{
  "language": "string",
  "version": "versionRange",          // e.g. "^5.3.0"
  "runtime": null | {name, version},  // null for Python/Go/Rust/Java
  "package-manager": {name, version}, // namedToolRange
  "frameworks": [{name, version}]     // array of namedToolRange
}
```

### When runtime is null
Languages where the compiler/interpreter IS the runtime:
- Python → `"runtime": null`
- Go → `"runtime": null`
- Rust → `"runtime": null`
- Java → `"runtime": null` (JVM is implicit)
- Ruby → `"runtime": {"name": "ruby", "version": "^3.2.0"}`

Languages with a separate runtime:
- TypeScript → `"runtime": {"name": "node", "version": ">=20.0.0"}`
- JavaScript → `"runtime": {"name": "node", "version": ">=20.0.0"}`
- CoffeeScript → `"runtime": {"name": "node", "version": "..."}`

### package-manager mapping

| Signal | name | version source |
|---|---|---|
| `packageManager: "pnpm@9.1.0"` in package.json | `"pnpm"` | `"^9.1.0"` |
| `pnpm-lock.yaml` exists | `"pnpm"` | Check packageManager field or use `">=8.0.0"` |
| `yarn.lock` exists | `"yarn"` | Check packageManager field |
| `package-lock.json` exists | `"npm"` | Check engines.npm or use `">=9.0.0"` |
| `[build-system] requires = ["poetry-core"]` | `"poetry"` | Check tool.poetry or use `">=1.7.0"` |
| `[build-system] requires = ["hatchling"]` | `"hatch"` | Use `">=1.0.0"` |
| `[build-system] requires = ["pdm-backend"]` | `"pdm"` | Use `">=2.0.0"` |
| `[build-system] requires = ["setuptools"]` | `"pip"` | Use `">=23.0.0"` |
| No Python build-system, just requirements.txt | `"pip"` | Use `">=23.0.0"` |
| `go.mod` | `"go-modules"` | Use Go version from `go.mod` |
| `Cargo.toml` | `"cargo"` | Use `">=1.0.0"` |

---

## dependencies

```json
{
  "update-strategy": "major-auto-merge" | "minor-auto-merge" | "patch-auto-merge" | "manual",
  "lock-files": "required" | "optional" | "forbidden",
  "allowed-licenses": ["MIT", "Apache-2.0", ...],  // array of strings
  "version-pinning": {
    "strategy": "minor-range" | "patch-range" | "exact",
    "exact-for": ["package-name", ...]  // optional array
  }
}
```

### Inference rules

- **update-strategy**: `renovate.json` or `dependabot.yml` → `"minor-auto-merge"` (safe default).
  No automated tool → `"manual"`.
- **lock-files**: Lock file present → `"required"`. `.npmrc` with `package-lock=false` → `"forbidden"`.
- **allowed-licenses**: Infer from root package.json `license` field. If `"MIT"`, use `["MIT"]`.
  If unsure, ask the user.
- **version-pinning.strategy**: Check dependency version prefixes. `^` → `"minor-range"`.
  `~` → `"patch-range"`. No prefix / exact → `"exact"`.

---

## deployment.tools

Array of **namedToolExact** objects (exact versions, not ranges):

```json
{
  "tools": [
    { "name": "docker", "version": "27.0.0" },
    { "name": "helm", "version": "3.14.0" },
    { "name": "terraform", "version": "1.7.0" },
    { "name": "kubernetes", "version": "1.30.0" }
  ]
}
```

**NOT strings.** `"tools": ["docker", "kubernetes"]` is invalid ❌

If exact versions aren't discoverable, use a reasonable current version.

---

## release

```json
{
  "versioning": "semver" | "calver",
  "changelog": "conventional-commits" | "keep-a-changelog" | "manual",
  "tagging": "per-service" | "monorepo"
}
```

- **tagging**: `"per-service"` for standalone projects or monorepos with independent versioning.
  `"monorepo"` only if all packages share a single version.

---

## security

All four tool entries are **required at the global level**. Each is a `securityToolEntry`:

```json
{
  "name": "string",              // required: tool identifier
  "version": "versionRange",     // optional
  "mode": "cli" | "saas" | "plugin",  // optional
  "config-path": "string"        // optional: repo-relative path
}
```

### Inferring from CI steps

| CI Pattern | Field | Value |
|---|---|---|
| `snyk/actions/node@master` | dependency-scanning | `{"name": "snyk", "mode": "cli"}` |
| `aquasecurity/trivy-action@master` | container-scanning | `{"name": "trivy", "mode": "cli"}` |
| `returntocorp/semgrep-action@v1` | sast | `{"name": "semgrep", "mode": "cli"}` |
| `gitleaks` in pre-commit hooks | secret-detection | `{"name": "gitleaks", "mode": "cli"}` |
| `run: npm audit` or `pip-audit` | dependency-scanning | `{"name": "npm-audit"}` or `{"name": "pip-audit"}` |

If a security tool category has no evidence at all, you still need to include it
(it's required at global level). Ask the user what they use.

---

## owner.team

Pattern: `^[a-z0-9]+(-[a-z0-9]+)*$`

### Parsing from CODEOWNERS

CODEOWNERS format: `path/ @org/team-name`

To extract team slug:
1. Take the part after `@org/` → `team-name`
2. Verify it matches the pattern (lowercase, kebab-case, no underscores)
3. If it contains underscores, convert to hyphens
4. If it contains uppercase, lowercase it

Examples:
- `@acme/platform-team` → `"platform-team"` ✅
- `@acme/Backend_Platform` → `"backend-platform"` (normalize)
- `@jsmith` → Not a team, skip (individual). Ask the user.

---

## service-communication

```json
{
  "internal-sync": "http-rest" | "grpc" | "graphql",
  "internal-async-protocol": "event-driven" | "message-queue",
  "internal-async-transport": {
    "protocol": "event-driven" | "message-queue",
    "broker": "kafka" | "rabbitmq" | "sqs" | "sns-sqs" | "nats" | "redis-streams" | "pulsar" | "azure-service-bus" | "google-pubsub",
    "serialization": "json" | "avro" | "protobuf" | "msgpack",
    "schema-registry": "string"  // optional
  }
}
```

### Celery mapping
Celery with Redis broker → `"broker": "redis-streams"`, `"protocol": "message-queue"`
Celery with RabbitMQ → `"broker": "rabbitmq"`, `"protocol": "message-queue"`
Celery with SQS → `"broker": "sqs"`, `"protocol": "message-queue"`
