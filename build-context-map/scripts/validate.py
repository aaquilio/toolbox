#!/usr/bin/env python3
"""
validate.py — Structural validator for build-context-map .context/ artifacts.

Runs as the final step of the skill. Exit code 0 = pass; 1 = validation failures
present; 2 = invocation/IO error.

Stdlib-only by design — no pip install step required.

Usage:
    python3 validate.py <context_dir> [--repo-root <path>]... [--json]

    <context_dir>    Path to the .context/ directory to validate.
    --repo-root      Repeatable. Path to a repo root that .context/ describes.
                     Used to resolve cited file paths and verify commits.
                     If omitted, file/citation existence checks are skipped
                     (the validator runs in front-matter-only mode).
    --json           Emit findings as JSON to stdout instead of human-readable text.

Findings categories (used by the orchestrator's repair pass):
    front_matter        Missing/invalid YAML front-matter
    schema              Front-matter does not match schema (field, type, enum)
    section_confidence  Section heading without confidence annotation
    high_no_citation    HIGH-confidence section without any citation
    broken_citation     Cited path:line does not resolve
    missing_path        Referenced file path does not exist
    orphan              File under .context/ not reachable from map.md
    index_missing       Subsystem/repo not indexed by parent
    date_order          updated < created
    bad_commit          Commit hash invalid or not in repo

Findings are reported with file path, line number (when applicable), category,
and message. The orchestrator's repair pass receives the JSON findings list as
input and is expected to fix as many as it can in a single pass.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Schema reference (in-source, kept aligned with resources/schema.json)
# ---------------------------------------------------------------------------

ALLOWED_CONFIDENCE = {"HIGH", "MEDIUM", "LOW"}
ALLOWED_REVIEW_DEPTH = {"none", "per_scope", "full"}

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
COMMIT_RE = re.compile(r"^([0-9a-f]{7,40}|none)$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(-[A-Za-z0-9.-]+)?$")
ORIGIN_RE = re.compile(r"^(none|https?://\S+|git@\S+|ssh://\S+|file://\S+)$")

REQUIRED_SCOPE_FIELDS = [
    "file", "scope", "created", "updated", "commit", "origin",
    "analyzer_version", "review_depth", "confidence",
]
REQUIRED_MAP_FIELDS = [
    "file", "scope", "created", "updated", "commit", "origins",
    "analyzer_version", "review_depth", "confidence",
]

# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    category: str
    file: str
    line: int | None
    message: str
    hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}

    def format_human(self) -> str:
        loc = f"{self.file}:{self.line}" if self.line else self.file
        out = f"[{self.category}] {loc}: {self.message}"
        if self.hint:
            out += f"\n    hint: {self.hint}"
        return out


# ---------------------------------------------------------------------------
# Minimal YAML front-matter parser (stdlib only)
#
# Supports the subset we actually emit:
#   key: scalar
#   key: "quoted scalar"
#   origins:
#     - name: url
#     - name2: url2
# Comments (# ...) and blank lines are ignored.
#
# We deliberately do NOT support nested mappings, multi-line scalars, anchors,
# or flow style — the schema doesn't require them and a real YAML parser is
# not in stdlib.
# ---------------------------------------------------------------------------

class FrontMatterError(Exception):
    def __init__(self, message: str, line: int):
        super().__init__(message)
        self.line = line


def parse_front_matter(text: str) -> tuple[dict[str, Any], int]:
    """
    Parse YAML front-matter from the start of `text`. Returns (data, end_line)
    where end_line is the 1-indexed line containing the closing '---'.

    Raises FrontMatterError if the front-matter is missing or malformed.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise FrontMatterError("missing opening '---' on line 1", 1)

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        raise FrontMatterError("missing closing '---'", len(lines))

    data: dict[str, Any] = {}
    current_list_key: str | None = None
    i = 1
    while i < end_idx:
        raw = lines[i]
        line_no = i + 1
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        # List item under a sequence key
        if stripped.startswith("- "):
            if current_list_key is None:
                raise FrontMatterError(
                    f"list item with no parent sequence key", line_no
                )
            item_text = stripped[2:].strip()
            # We expect single-key mappings: "name: url"
            if ":" in item_text:
                k, _, v = item_text.partition(":")
                data[current_list_key].append({k.strip(): _unquote(v.strip())})
            else:
                data[current_list_key].append(_unquote(item_text))
            i += 1
            continue

        # key: value (or key: with following list)
        if ":" not in stripped:
            raise FrontMatterError(f"expected 'key: value', got {stripped!r}", line_no)
        k, _, v = stripped.partition(":")
        key = k.strip()
        value = v.strip()

        if value == "":
            # Could be a sequence key; peek ahead
            j = i + 1
            while j < end_idx and not lines[j].strip():
                j += 1
            if j < end_idx and lines[j].strip().startswith("- "):
                data[key] = []
                current_list_key = key
                i += 1
                continue
            else:
                data[key] = ""
                current_list_key = None
                i += 1
                continue

        data[key] = _unquote(value)
        current_list_key = None
        i += 1

    return data, end_idx + 1


def _unquote(s: str) -> str:
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    return s


# ---------------------------------------------------------------------------
# Schema validation (front-matter shape)
# ---------------------------------------------------------------------------

def validate_front_matter(data: dict[str, Any], file: str, is_map: bool) -> list[Finding]:
    findings: list[Finding] = []
    required = REQUIRED_MAP_FIELDS if is_map else REQUIRED_SCOPE_FIELDS

    for f in required:
        if f not in data:
            findings.append(Finding(
                category="schema",
                file=file,
                line=1,
                message=f"required field missing: {f!r}",
                hint=f"add {f}: ... to the front-matter block",
            ))

    # Extra-fields check
    allowed = set(required)
    for k in data:
        if k not in allowed:
            findings.append(Finding(
                category="schema",
                file=file,
                line=1,
                message=f"unexpected field: {k!r}",
            ))

    # Per-field validation
    def check(field_name: str, fn, msg: str):
        if field_name in data and not fn(data[field_name]):
            findings.append(Finding(
                category="schema",
                file=file,
                line=1,
                message=f"{field_name!r}: {msg} (got {data[field_name]!r})",
            ))

    check("file", lambda v: isinstance(v, str) and v.startswith(".context/"),
          "must be a string starting with '.context/'")
    check("scope", lambda v: isinstance(v, str) and len(v) > 0,
          "must be a non-empty string")
    check("created", lambda v: isinstance(v, str) and bool(ISO_DATE_RE.match(v)),
          "must be ISO date YYYY-MM-DD")
    check("updated", lambda v: isinstance(v, str) and bool(ISO_DATE_RE.match(v)),
          "must be ISO date YYYY-MM-DD")
    check("commit", lambda v: isinstance(v, str) and bool(COMMIT_RE.match(v)),
          "must be 7-40 hex chars or 'none'")
    check("analyzer_version", lambda v: isinstance(v, str) and bool(SEMVER_RE.match(v)),
          "must be semver")
    check("review_depth", lambda v: v in ALLOWED_REVIEW_DEPTH,
          f"must be one of {sorted(ALLOWED_REVIEW_DEPTH)}")
    check("confidence", lambda v: v in ALLOWED_CONFIDENCE,
          f"must be one of {sorted(ALLOWED_CONFIDENCE)}")

    if is_map:
        if "origins" in data:
            v = data["origins"]
            if not isinstance(v, list) or not v:
                findings.append(Finding(
                    category="schema",
                    file=file,
                    line=1,
                    message="'origins': must be a non-empty list",
                ))
            else:
                for entry in v:
                    if not isinstance(entry, dict) or len(entry) != 1:
                        findings.append(Finding(
                            category="schema",
                            file=file,
                            line=1,
                            message=f"'origins' entry must be a single-key mapping, got {entry!r}",
                        ))
                        continue
                    url = next(iter(entry.values()))
                    if not (isinstance(url, str) and ORIGIN_RE.match(url)):
                        findings.append(Finding(
                            category="schema",
                            file=file,
                            line=1,
                            message=f"'origins' URL invalid: {url!r}",
                        ))
    else:
        check("origin", lambda v: isinstance(v, str) and bool(ORIGIN_RE.match(v)),
              "must be a URL or 'none'")

    # Date ordering
    if "created" in data and "updated" in data:
        c, u = data.get("created"), data.get("updated")
        if isinstance(c, str) and isinstance(u, str) and ISO_DATE_RE.match(c) and ISO_DATE_RE.match(u):
            if u < c:
                findings.append(Finding(
                    category="date_order",
                    file=file,
                    line=1,
                    message=f"updated ({u}) is earlier than created ({c})",
                ))

    return findings


# ---------------------------------------------------------------------------
# Body scanning: section confidence, citations, paths
# ---------------------------------------------------------------------------

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
CONFIDENCE_RE = re.compile(r"^<!--\s*confidence:\s*(HIGH|MEDIUM|LOW)\s*-->\s*$")

# A citation is `path:line` or `path:line-line` inside backticks.
# The path must contain at least one '.' (extension) or '/' to avoid matching
# noun:line constructs in prose.
CITATION_RE = re.compile(
    r"`([^`\s]+(?:[./][^`\s]*)+):(\d+)(?:-(\d+))?`"
)

# Any backticked code span that looks like a file path: contains '/' or
# ends with a known source-file extension. Used for missing_path checks.
PATH_LIKE_RE = re.compile(
    r"`([^`\s]+(?:/[^`\s]+|\.(?:[a-zA-Z]{1,5}))+)`"
)


@dataclass
class Section:
    heading_line: int
    title: str
    confidence: str | None
    confidence_line: int | None
    body_start: int
    body_end: int
    text: str = field(default="")


def split_sections(body_lines: list[str], body_start_line: int) -> list[Section]:
    """
    Split markdown body into sections by ATX headings. Each Section captures
    its confidence annotation (or None), and its body text.

    body_start_line is the 1-indexed line where body_lines begins in the file.
    """
    sections: list[Section] = []
    current: Section | None = None

    for idx, line in enumerate(body_lines):
        line_no = body_start_line + idx
        m = HEADING_RE.match(line)
        if m:
            if current is not None:
                current.body_end = line_no - 1
                sections.append(current)
            current = Section(
                heading_line=line_no,
                title=m.group(2).strip(),
                confidence=None,
                confidence_line=None,
                body_start=line_no + 1,
                body_end=line_no,
            )
            continue

        if current is not None:
            # Confidence annotation must be on the line immediately after heading,
            # ignoring blank lines.
            if current.confidence is None and line.strip() != "":
                cm = CONFIDENCE_RE.match(line.strip())
                if cm:
                    current.confidence = cm.group(1)
                    current.confidence_line = line_no

    if current is not None:
        current.body_end = body_start_line + len(body_lines) - 1
        sections.append(current)

    # Attach text
    for s in sections:
        rel_start = s.body_start - body_start_line
        rel_end = s.body_end - body_start_line + 1
        rel_start = max(0, rel_start)
        rel_end = min(len(body_lines), rel_end)
        s.text = "\n".join(body_lines[rel_start:rel_end])

    return sections


def scan_body(
    md_path: Path,
    file_label: str,
    body_lines: list[str],
    body_start_line: int,
    scope_root: Path | None,
) -> list[Finding]:
    """
    Walk sections, check confidence annotations, citations, and path references.
    """
    findings: list[Finding] = []
    sections = split_sections(body_lines, body_start_line)

    for sec in sections:
        # Section confidence annotation
        if sec.confidence is None:
            findings.append(Finding(
                category="section_confidence",
                file=file_label,
                line=sec.heading_line,
                message=f"section {sec.title!r} missing '<!-- confidence: ... -->' annotation",
                hint="add a confidence comment on the line immediately after the heading",
            ))

        # HIGH sections must contain at least one citation
        if sec.confidence == "HIGH":
            citations = list(CITATION_RE.finditer(sec.text))
            if not citations:
                findings.append(Finding(
                    category="high_no_citation",
                    file=file_label,
                    line=sec.heading_line,
                    message=f"HIGH-confidence section {sec.title!r} contains no `path:line` citations",
                    hint="downgrade to MEDIUM or add at least one citation",
                ))

        # Citation resolution (only if we have a scope root to resolve against)
        if scope_root is not None:
            for m in CITATION_RE.finditer(sec.text):
                path_str, start_s, end_s = m.group(1), m.group(2), m.group(3)
                # Compute line number of the citation within the file
                citation_line = _line_of_offset(sec.text, m.start(), sec.body_start)
                try:
                    start_line = int(start_s)
                    end_line = int(end_s) if end_s else start_line
                except ValueError:
                    findings.append(Finding(
                        category="broken_citation",
                        file=file_label,
                        line=citation_line,
                        message=f"citation has non-integer line number: `{path_str}:{start_s}{'-'+end_s if end_s else ''}`",
                    ))
                    continue
                if end_line < start_line:
                    findings.append(Finding(
                        category="broken_citation",
                        file=file_label,
                        line=citation_line,
                        message=f"citation range inverted: `{path_str}:{start_s}-{end_s}`",
                    ))
                    continue

                resolved = (scope_root / path_str).resolve()
                if not resolved.is_file():
                    findings.append(Finding(
                        category="broken_citation",
                        file=file_label,
                        line=citation_line,
                        message=f"cited file does not exist: {path_str}",
                    ))
                    continue
                try:
                    with open(resolved, "rb") as fh:
                        line_count = sum(1 for _ in fh)
                except OSError as e:
                    findings.append(Finding(
                        category="broken_citation",
                        file=file_label,
                        line=citation_line,
                        message=f"could not read cited file {path_str}: {e}",
                    ))
                    continue
                if start_line < 1 or end_line > line_count:
                    findings.append(Finding(
                        category="broken_citation",
                        file=file_label,
                        line=citation_line,
                        message=f"line out of range: {path_str} has {line_count} lines, "
                                f"citation requests {start_line}-{end_line}",
                    ))

            # Path-like backticked spans that are NOT citations: check existence
            for m in PATH_LIKE_RE.finditer(sec.text):
                span = m.group(1)
                # Skip citations (already handled)
                full_match = m.group(0)
                if CITATION_RE.match(full_match):
                    continue
                # Skip obvious non-paths
                if span.startswith(("http://", "https://", "git@", "ssh://")):
                    continue
                # Skip env var names, config keys, etc. — heuristic: must contain '/' or end in source extension
                if "/" not in span and not _looks_like_filename(span):
                    continue
                path_line = _line_of_offset(sec.text, m.start(), sec.body_start)
                resolved = (scope_root / span).resolve()
                if not resolved.exists():
                    findings.append(Finding(
                        category="missing_path",
                        file=file_label,
                        line=path_line,
                        message=f"referenced path does not exist: {span}",
                        hint="if intentional (historical reference), annotate it; otherwise fix the path",
                    ))

    return findings


def _line_of_offset(text: str, offset: int, base_line: int) -> int:
    return base_line + text.count("\n", 0, offset)


_SOURCE_EXT_RE = re.compile(
    r"\.(py|js|jsx|ts|tsx|go|rs|java|kt|swift|rb|php|cs|cpp|c|h|hpp|"
    r"sql|yml|yaml|toml|json|md|sh|bash|zsh|proto|graphql|gql|tf)$"
)

def _looks_like_filename(s: str) -> bool:
    return bool(_SOURCE_EXT_RE.search(s))


# ---------------------------------------------------------------------------
# Cross-file structural checks
# ---------------------------------------------------------------------------

def check_indices_and_orphans(
    context_dir: Path,
) -> tuple[list[Finding], dict[str, str]]:
    """
    Verify that every $REPO/$SUBSYSTEM/context.md is referenced by its parent
    $REPO/context.md, and that every $REPO/context.md is referenced by map.md.
    Also reports orphans: any .md under .context/ (excluding .scratch/, .handoff/)
    that no parent index references.

    Returns (findings, file_label_map).
    """
    findings: list[Finding] = []
    map_path = context_dir / "map.md"
    if not map_path.is_file():
        findings.append(Finding(
            category="orphan",
            file=str(map_path.relative_to(context_dir.parent)),
            line=None,
            message="map.md does not exist",
        ))
        return findings, {}

    map_text = map_path.read_text(encoding="utf-8", errors="replace")

    # Discover all repo dirs (immediate children with a context.md)
    repo_dirs = [d for d in context_dir.iterdir()
                 if d.is_dir() and not d.name.startswith(".")
                 and (d / "context.md").is_file()]

    # Repo index check: each repo name should appear in map.md
    for rd in repo_dirs:
        if rd.name not in map_text:
            findings.append(Finding(
                category="index_missing",
                file=str(map_path.relative_to(context_dir.parent)),
                line=None,
                message=f"repo {rd.name!r} is not referenced in map.md",
                hint=f"add an entry for {rd.name} to the repo index in map.md",
            ))

    # Subsystem index check: each subsystem dir should appear in its parent context.md
    for rd in repo_dirs:
        repo_ctx_path = rd / "context.md"
        repo_ctx_text = repo_ctx_path.read_text(encoding="utf-8", errors="replace")
        sub_dirs = [d for d in rd.iterdir()
                    if d.is_dir() and not d.name.startswith(".")
                    and (d / "context.md").is_file()]
        for sd in sub_dirs:
            if sd.name not in repo_ctx_text:
                findings.append(Finding(
                    category="index_missing",
                    file=str(repo_ctx_path.relative_to(context_dir.parent)),
                    line=None,
                    message=f"subsystem {sd.name!r} is not referenced in {rd.name}/context.md",
                    hint=f"add a subsystem-index entry for {sd.name}",
                ))

    # Orphan detection: find every .md under .context/ that is not map.md,
    # not a known repo context.md, and not a known subsystem context.md.
    expected: set[Path] = {map_path}
    for rd in repo_dirs:
        expected.add(rd / "context.md")
        for sd in rd.iterdir():
            if sd.is_dir() and not sd.name.startswith("."):
                cm = sd / "context.md"
                if cm.is_file():
                    expected.add(cm)

    for p in context_dir.rglob("*.md"):
        # Skip transient dirs
        rel = p.relative_to(context_dir)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if p not in expected:
            findings.append(Finding(
                category="orphan",
                file=str(p.relative_to(context_dir.parent)),
                line=None,
                message="file is under .context/ but is not reachable from map.md",
                hint="either reference it from a parent index, move it under .scratch/, or delete it",
            ))

    return findings, {}


# ---------------------------------------------------------------------------
# Commit verification (optional, when repo roots are provided)
# ---------------------------------------------------------------------------

def verify_commit(commit: str, repo_root: Path) -> bool:
    if commit == "none":
        return True
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "cat-file", "-e", commit + "^{commit}"],
            capture_output=True,
            check=False,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return True  # don't fail validation if git isn't available


# ---------------------------------------------------------------------------
# Per-file driver
# ---------------------------------------------------------------------------

def validate_file(
    md_path: Path,
    context_dir: Path,
    repo_roots: list[Path],
) -> list[Finding]:
    file_label = str(md_path.relative_to(context_dir.parent))
    try:
        text = md_path.read_text(encoding="utf-8")
    except OSError as e:
        return [Finding(category="front_matter", file=file_label, line=None,
                        message=f"could not read file: {e}")]

    findings: list[Finding] = []
    is_map = md_path.name == "map.md" and md_path.parent == context_dir

    try:
        data, fm_end = parse_front_matter(text)
    except FrontMatterError as e:
        findings.append(Finding(
            category="front_matter",
            file=file_label,
            line=e.line,
            message=str(e),
            hint="every context.md must begin with a YAML front-matter block",
        ))
        return findings

    findings.extend(validate_front_matter(data, file_label, is_map=is_map))

    # Resolve scope root for citation/path checks
    scope_root: Path | None = None
    scope_value = data.get("scope")
    if scope_value and repo_roots:
        # Try to match scope to one of the repo roots
        for rr in repo_roots:
            if Path(scope_value) == rr or rr.name == Path(scope_value).parts[0]:
                scope_root = rr
                break
        if scope_root is None:
            # Fall back: if there's exactly one repo root, use it
            if len(repo_roots) == 1:
                scope_root = repo_roots[0]

    # Body scan
    body_lines = text.splitlines()[fm_end:]
    body_start_line = fm_end + 1
    findings.extend(scan_body(md_path, file_label, body_lines, body_start_line, scope_root))

    # Commit verification
    commit = data.get("commit")
    if commit and scope_root and isinstance(commit, str):
        if not verify_commit(commit, scope_root):
            findings.append(Finding(
                category="bad_commit",
                file=file_label,
                line=1,
                message=f"commit {commit!r} not found in repo {scope_root}",
            ))

    return findings


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("context_dir", help="Path to .context/ directory")
    parser.add_argument("--repo-root", action="append", default=[],
                        help="Path to a repo root (repeatable)")
    parser.add_argument("--json", action="store_true", help="Emit JSON findings")
    args = parser.parse_args(argv)

    context_dir = Path(args.context_dir).resolve()
    if not context_dir.is_dir():
        print(f"error: {context_dir} is not a directory", file=sys.stderr)
        return 2
    if context_dir.name != ".context":
        print(f"warning: directory name is {context_dir.name!r}, expected '.context'",
              file=sys.stderr)

    repo_roots = [Path(r).resolve() for r in args.repo_root]
    for rr in repo_roots:
        if not rr.is_dir():
            print(f"error: repo root {rr} is not a directory", file=sys.stderr)
            return 2

    all_findings: list[Finding] = []

    # Per-file checks
    for md in sorted(context_dir.rglob("*.md")):
        rel = md.relative_to(context_dir)
        if any(part.startswith(".") for part in rel.parts):
            continue
        all_findings.extend(validate_file(md, context_dir, repo_roots))

    # Cross-file checks
    cross_findings, _ = check_indices_and_orphans(context_dir)
    all_findings.extend(cross_findings)

    # Output
    if args.json:
        json.dump(
            {
                "ok": len(all_findings) == 0,
                "findings_count": len(all_findings),
                "findings": [f.to_dict() for f in all_findings],
            },
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
    else:
        if not all_findings:
            print(f"OK: {context_dir} passed validation")
        else:
            print(f"FAIL: {context_dir} — {len(all_findings)} finding(s)")
            print()
            for f in all_findings:
                print(f.format_human())
                print()

    return 0 if not all_findings else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
