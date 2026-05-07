#!/usr/bin/env python3
"""
validate-trace.py — Structural validator for trace outputs.

Runs as the deterministic half of Phase 5 (the LLM validator handles the rest).
Stdlib-only.

Usage:
    python3 validate-trace.py <trace_path> [--repo-root <path>]... [--json]

    <trace_path>   Path to the trace .md file (or a draft on disk).
    --repo-root    Repeatable. Path to a repo root for citation resolution.
                   Without this, citation existence is not checked.
    --json         Emit findings as JSON instead of human-readable text.

Exit codes:
    0   no findings
    1   findings present
    2   invocation/IO error

Finding categories:
    front_matter        Missing/invalid YAML front-matter
    schema              Front-matter does not match schema
    preamble            Missing or malformed '**Trace:** ...' preamble
    section_confidence  Section heading without confidence annotation
    high_no_citation    HIGH section without any path:line citation
    broken_citation     Cited path:line does not resolve
    missing_section     Required section for input_type is missing
    overall_summary     Missing or malformed 'Overall: ...' summary
    staleness_note      Trace was warned-stale but lacks 'Staleness Notes' section
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
# Schema constants (kept aligned with resources/trace-schema.json)
# ---------------------------------------------------------------------------

ALLOWED_CONFIDENCE = {"HIGH", "MEDIUM", "LOW"}
ALLOWED_INPUT_TYPE = {"question", "bug", "feature", "refactor"}
ALLOWED_VERDICT = {"PASS", "REVISE", "REVISED", "DISAGREEMENT_SURFACED"}
ALLOWED_STALENESS = {"fresh", "warned", "refreshed"}

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
COMMIT_RE = re.compile(r"^([0-9a-f]{7,40}|none)$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(-[A-Za-z0-9.-]+)?$")

REQUIRED_FRONT_MATTER = [
    "file", "trace_input", "input_type", "created", "trace_skill_version",
    "context_commit_alignment", "files_consulted", "overall_confidence",
    "validator_verdict",
]

OPTIONAL_FRONT_MATTER = ["prior_trace_consulted", "depends_on"]

REQUIRED_SECTIONS = {
    "question": ["How", "Entry Point", "Flow"],  # match by heading prefix
    "bug": ["Diagnosis", "Root Cause", "Fix Design", "Side Effects", "Verification"],
    "feature": ["Design Summary", "Insertion Points", "Interface Contracts",
                "Implementation Sequence", "Risks"],
    "refactor": ["Current State", "Target State", "Migration Plan", "Risk Assessment"],
}

PREAMBLE_RE = re.compile(r"^\*\*Trace:\*\*\s+.+\s+·\s+(question|bug|feature|refactor)\s+·\s+via\s+.+$")
OVERALL_RE = re.compile(
    r"^Overall:\s+(HIGH|MEDIUM|LOW)\s+\((\d+)\s+HIGH,\s+(\d+)\s+MEDIUM,\s+(\d+)\s+LOW\)\s*$"
)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
CONFIDENCE_RE = re.compile(r"^<!--\s*confidence:\s*(HIGH|MEDIUM|LOW)\s*-->\s*$")
CITATION_RE = re.compile(
    r"`([^`\s]+(?:[./][^`\s]*)+):(\d+)(?:-(\d+))?`"
)


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
# Front-matter parsing (stdlib YAML subset)
# ---------------------------------------------------------------------------

class FrontMatterError(Exception):
    def __init__(self, message: str, line: int):
        super().__init__(message)
        self.line = line


def parse_front_matter(text: str) -> tuple[dict[str, Any], int]:
    """
    Parse YAML front-matter at the top of `text`. Returns (data, end_line_1indexed).

    Supports:
        key: scalar
        key: "quoted"
        key:
          subkey: value
          subkey2: value2
        list_key:
          - scalar
          - {single-key: mapping}
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
    i = 1

    def indent_of(s: str) -> int:
        return len(s) - len(s.lstrip(" "))

    while i < end_idx:
        raw = lines[i]
        line_no = i + 1
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        if ":" not in stripped:
            raise FrontMatterError(f"expected 'key: value', got {stripped!r}", line_no)
        k, _, v = stripped.partition(":")
        key = k.strip()
        value = v.strip()
        my_indent = indent_of(raw)

        if value == "":
            # Could be a sequence or a nested mapping; peek
            j = i + 1
            while j < end_idx and not lines[j].strip():
                j += 1
            if j >= end_idx:
                data[key] = ""
                i += 1
                continue
            child_indent = indent_of(lines[j])
            if child_indent <= my_indent:
                data[key] = ""
                i += 1
                continue

            if lines[j].lstrip().startswith("- "):
                # Sequence — items may be multi-line with nested keys
                seq: list[Any] = []
                while j < end_idx:
                    if not lines[j].strip():
                        j += 1
                        continue
                    if indent_of(lines[j]) < child_indent:
                        break
                    if not (indent_of(lines[j]) == child_indent and lines[j].lstrip().startswith("- ")):
                        break
                    # Start of a new sequence item
                    first_item_line = lines[j].lstrip()[2:]
                    item_indent = child_indent + 2  # past "- "
                    item_dict: dict[str, Any] | None = None
                    item_scalar: Any | None = None

                    if first_item_line.strip() == "":
                        item_dict = {}
                    elif ":" in first_item_line and not first_item_line.strip().startswith("#"):
                        ik, _, iv = first_item_line.partition(":")
                        ik = ik.strip()
                        iv_stripped = iv.strip()
                        item_dict = {}
                        if iv_stripped == "":
                            # Nested under this key — handled below by continuation
                            item_dict[ik] = None  # placeholder
                            pending_nested_key = ik
                        else:
                            item_dict[ik] = _unquote(iv_stripped)
                            pending_nested_key = None
                    else:
                        item_scalar = _unquote(first_item_line.strip())

                    j += 1

                    # Collect continuation lines: indented MORE than child_indent and not a new "- "
                    while j < end_idx:
                        if not lines[j].strip():
                            j += 1
                            continue
                        cur_indent = indent_of(lines[j])
                        if cur_indent <= child_indent:
                            break
                        # Continuation belongs to this item
                        cont = lines[j].lstrip()
                        if ":" not in cont:
                            # Could be a list value under a pending nested key; not supported here
                            j += 1
                            continue
                        ck, _, cv = cont.partition(":")
                        ck = ck.strip()
                        cv_stripped = cv.strip()
                        if cv_stripped == "":
                            # The next thing should be a sub-list. Gather it.
                            sub_indent_probe = j + 1
                            while sub_indent_probe < end_idx and not lines[sub_indent_probe].strip():
                                sub_indent_probe += 1
                            sub_list: list[Any] = []
                            if (sub_indent_probe < end_idx
                                and indent_of(lines[sub_indent_probe]) > cur_indent
                                and lines[sub_indent_probe].lstrip().startswith("- ")):
                                sub_indent = indent_of(lines[sub_indent_probe])
                                k2 = sub_indent_probe
                                while k2 < end_idx:
                                    if not lines[k2].strip():
                                        k2 += 1
                                        continue
                                    if indent_of(lines[k2]) < sub_indent or not lines[k2].lstrip().startswith("- "):
                                        break
                                    sub_list.append(_unquote(lines[k2].lstrip()[2:].strip()))
                                    k2 += 1
                                if item_dict is None:
                                    item_dict = {}
                                item_dict[ck] = sub_list
                                j = k2
                                continue
                            else:
                                if item_dict is None:
                                    item_dict = {}
                                item_dict[ck] = ""
                                j += 1
                                continue
                        else:
                            if item_dict is None:
                                item_dict = {}
                            item_dict[ck] = _unquote(cv_stripped)
                            j += 1

                    if item_dict is not None:
                        seq.append(item_dict)
                    elif item_scalar is not None:
                        seq.append(item_scalar)

                data[key] = seq
                i = j
                continue
            else:
                # Nested mapping
                nested: dict[str, Any] = {}
                while j < end_idx and (not lines[j].strip() or indent_of(lines[j]) >= child_indent):
                    if not lines[j].strip():
                        j += 1
                        continue
                    if indent_of(lines[j]) < child_indent:
                        break
                    inner = lines[j].strip()
                    if ":" not in inner:
                        raise FrontMatterError(f"expected 'key: value' in nested map, got {inner!r}", j + 1)
                    nk, _, nv = inner.partition(":")
                    nv = nv.strip()
                    if nv == "":
                        # Two-deep nested mapping
                        deeper: dict[str, Any] = {}
                        k2 = j + 1
                        while k2 < end_idx and not lines[k2].strip():
                            k2 += 1
                        if k2 < end_idx and indent_of(lines[k2]) > child_indent:
                            deep_indent = indent_of(lines[k2])
                            while k2 < end_idx and (not lines[k2].strip() or indent_of(lines[k2]) >= deep_indent):
                                if not lines[k2].strip():
                                    k2 += 1
                                    continue
                                if indent_of(lines[k2]) < deep_indent:
                                    break
                                di = lines[k2].strip()
                                if ":" not in di:
                                    raise FrontMatterError(f"expected 'key: value' in deep map, got {di!r}", k2 + 1)
                                dk, _, dv = di.partition(":")
                                deeper[dk.strip()] = _unquote(dv.strip())
                                k2 += 1
                        nested[nk.strip()] = deeper
                        j = k2
                    else:
                        nested[nk.strip()] = _unquote(nv)
                        j += 1
                data[key] = nested
                i = j
                continue
        else:
            data[key] = _unquote(value)
            i += 1

    return data, end_idx + 1


def _unquote(s: str) -> str:
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    return s


# ---------------------------------------------------------------------------
# Front-matter schema validation
# ---------------------------------------------------------------------------

def validate_front_matter(data: dict[str, Any], file: str) -> list[Finding]:
    findings: list[Finding] = []

    for f in REQUIRED_FRONT_MATTER:
        if f not in data:
            findings.append(Finding("schema", file, 1,
                                    f"required field missing: {f!r}",
                                    hint=f"add {f}: ... to front-matter"))

    allowed = set(REQUIRED_FRONT_MATTER) | set(OPTIONAL_FRONT_MATTER)
    for k in data:
        if k not in allowed:
            findings.append(Finding("schema", file, 1, f"unexpected field: {k!r}"))

    def check(name: str, fn, msg: str):
        if name in data and not fn(data[name]):
            findings.append(Finding("schema", file, 1,
                                    f"{name!r}: {msg} (got {data[name]!r})"))

    check("file", lambda v: isinstance(v, str) and v.startswith(".context/traces/"),
          "must be a string starting with '.context/traces/'")
    check("trace_input", lambda v: isinstance(v, str) and len(v) > 0,
          "must be non-empty string")
    check("input_type", lambda v: v in ALLOWED_INPUT_TYPE,
          f"must be one of {sorted(ALLOWED_INPUT_TYPE)}")
    check("created", lambda v: isinstance(v, str) and bool(ISO_DATE_RE.match(v)),
          "must be ISO date YYYY-MM-DD")
    check("trace_skill_version", lambda v: isinstance(v, str) and bool(SEMVER_RE.match(v)),
          "must be semver")
    check("overall_confidence", lambda v: v in ALLOWED_CONFIDENCE,
          f"must be one of {sorted(ALLOWED_CONFIDENCE)}")
    check("validator_verdict", lambda v: v in ALLOWED_VERDICT,
          f"must be one of {sorted(ALLOWED_VERDICT)}")

    if "context_commit_alignment" in data:
        cca = data["context_commit_alignment"]
        if not isinstance(cca, dict):
            findings.append(Finding("schema", file, 1,
                                    "'context_commit_alignment' must be a mapping"))
        else:
            for repo, info in cca.items():
                if not isinstance(info, dict):
                    findings.append(Finding("schema", file, 1,
                                            f"context_commit_alignment[{repo!r}]: must be a mapping"))
                    continue
                for sub in ("context_commit", "head_commit", "staleness"):
                    if sub not in info:
                        findings.append(Finding("schema", file, 1,
                                                f"context_commit_alignment[{repo!r}]: missing {sub!r}"))
                if "staleness" in info and info["staleness"] not in ALLOWED_STALENESS:
                    findings.append(Finding("schema", file, 1,
                                            f"context_commit_alignment[{repo!r}].staleness: must be one of {sorted(ALLOWED_STALENESS)}"))
                for sub in ("context_commit", "head_commit"):
                    if sub in info and not COMMIT_RE.match(str(info[sub])):
                        findings.append(Finding("schema", file, 1,
                                                f"context_commit_alignment[{repo!r}].{sub}: invalid commit hash"))

    if "files_consulted" in data:
        fc = data["files_consulted"]
        if not isinstance(fc, list) or not fc:
            findings.append(Finding("schema", file, 1,
                                    "'files_consulted' must be a non-empty list"))

    return findings


# ---------------------------------------------------------------------------
# Body checks
# ---------------------------------------------------------------------------

@dataclass
class Section:
    heading_line: int
    title: str
    level: int
    confidence: str | None
    body_start: int
    body_end: int
    text: str = field(default="")


def split_sections(body_lines: list[str], body_start_line: int) -> list[Section]:
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
                level=len(m.group(1)),
                confidence=None,
                body_start=line_no + 1,
                body_end=line_no,
            )
            continue
        if current is not None and current.confidence is None and line.strip():
            cm = CONFIDENCE_RE.match(line.strip())
            if cm:
                current.confidence = cm.group(1)

    if current is not None:
        current.body_end = body_start_line + len(body_lines) - 1
        sections.append(current)

    for s in sections:
        rs = max(0, s.body_start - body_start_line)
        re_ = min(len(body_lines), s.body_end - body_start_line + 1)
        s.text = "\n".join(body_lines[rs:re_])
    return sections


def check_preamble(body_lines: list[str], body_start_line: int, file: str) -> list[Finding]:
    """Find the first non-blank, non-H1 line and verify it matches the preamble pattern."""
    findings: list[Finding] = []
    found_h1 = False
    for idx, line in enumerate(body_lines):
        line_no = body_start_line + idx
        if not line.strip():
            continue
        if line.strip().startswith("# ") and not found_h1:
            found_h1 = True
            continue
        # First non-H1 non-blank line
        if not PREAMBLE_RE.match(line.strip()):
            findings.append(Finding(
                "preamble", file, line_no,
                "preamble line missing or malformed",
                hint="expected: '**Trace:** <input> · <type> · via <files>'",
            ))
        return findings
    findings.append(Finding("preamble", file, None,
                            "no preamble found in body"))
    return findings


def check_required_sections(sections: list[Section], input_type: str, file: str) -> list[Finding]:
    findings: list[Finding] = []
    required = REQUIRED_SECTIONS.get(input_type, [])
    titles = [s.title for s in sections]
    for req in required:
        if not any(req.lower() in t.lower() for t in titles):
            findings.append(Finding(
                "missing_section", file, None,
                f"required section for input_type={input_type!r} not found: {req!r}",
                hint=f"add a section heading containing {req!r}",
            ))
    return findings


def check_section_confidences(sections: list[Section], file: str) -> list[Finding]:
    """Confidence annotations are required on level-2 sections (the real
    content sections). Level-1 is the document title; level-3+ are
    subsections that inherit their parent's confidence."""
    findings: list[Finding] = []
    for s in sections:
        if s.level != 2:
            continue
        if s.confidence is None:
            findings.append(Finding(
                "section_confidence", file, s.heading_line,
                f"section {s.title!r} missing '<!-- confidence: ... -->' annotation",
            ))
    return findings


def check_high_citations(sections: list[Section], file: str) -> list[Finding]:
    findings: list[Finding] = []
    for s in sections:
        if s.level != 2:
            continue
        if s.confidence == "HIGH":
            if not CITATION_RE.search(s.text):
                findings.append(Finding(
                    "high_no_citation", file, s.heading_line,
                    f"HIGH section {s.title!r} has no `path:line` citations",
                    hint="downgrade to MEDIUM or add a citation",
                ))
    return findings


def check_overall_summary(body_lines: list[str], file: str) -> list[Finding]:
    """Look for 'Overall: <CONF> (N HIGH, M MEDIUM, K LOW)' near the end."""
    for line in reversed(body_lines):
        s = line.strip()
        if not s:
            continue
        if OVERALL_RE.match(s):
            return []
        # Allow it to be inside a heading like '## Overall' followed by the summary line
        if s.startswith("Overall:"):
            return [Finding("overall_summary", file, None,
                            f"'Overall:' line malformed: {s!r}",
                            hint="expected: 'Overall: <CONF> (N HIGH, M MEDIUM, K LOW)'")]
        break
    return [Finding("overall_summary", file, None,
                    "missing 'Overall: ...' summary line")]


def check_staleness_note(
    sections: list[Section],
    front_matter: dict[str, Any],
    file: str,
) -> list[Finding]:
    cca = front_matter.get("context_commit_alignment", {}) or {}
    any_warned = False
    if isinstance(cca, dict):
        for repo, info in cca.items():
            if isinstance(info, dict) and info.get("staleness") == "warned":
                any_warned = True
                break
    if not any_warned:
        return []
    if any("staleness" in s.title.lower() for s in sections):
        return []
    return [Finding(
        "staleness_note", file, None,
        "trace produced under staleness warnings but lacks 'Staleness Notes' section",
        hint="add a section titled 'Staleness Notes' before the Overall summary",
    )]


def resolve_citations(
    sections: list[Section],
    file_label: str,
    repo_roots: list[Path],
) -> list[Finding]:
    findings: list[Finding] = []
    if not repo_roots:
        return findings
    for s in sections:
        for m in CITATION_RE.finditer(s.text):
            path_str, start_s, end_s = m.group(1), m.group(2), m.group(3)
            try:
                start_line = int(start_s)
                end_line = int(end_s) if end_s else start_line
            except ValueError:
                findings.append(Finding(
                    "broken_citation", file_label, s.heading_line,
                    f"citation has non-integer line: `{path_str}:{start_s}{'-'+end_s if end_s else ''}`",
                ))
                continue
            if end_line < start_line:
                findings.append(Finding(
                    "broken_citation", file_label, s.heading_line,
                    f"citation range inverted: `{path_str}:{start_s}-{end_s}`",
                ))
                continue
            resolved = None
            for rr in repo_roots:
                cand = (rr / path_str)
                if cand.is_file():
                    resolved = cand
                    break
                # Also allow paths prefixed with the repo dir name
                if Path(path_str).parts and Path(path_str).parts[0] == rr.name:
                    cand = rr.parent / path_str
                    if cand.is_file():
                        resolved = cand
                        break
            if resolved is None:
                findings.append(Finding(
                    "broken_citation", file_label, s.heading_line,
                    f"cited file not found in any repo root: {path_str}",
                ))
                continue
            try:
                with open(resolved, "rb") as fh:
                    line_count = sum(1 for _ in fh)
            except OSError as e:
                findings.append(Finding(
                    "broken_citation", file_label, s.heading_line,
                    f"could not read {path_str}: {e}",
                ))
                continue
            if start_line < 1 or end_line > line_count:
                findings.append(Finding(
                    "broken_citation", file_label, s.heading_line,
                    f"line out of range: {path_str} has {line_count} lines, citation requests {start_line}-{end_line}",
                ))
    return findings


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def validate_trace(trace_path: Path, repo_roots: list[Path]) -> list[Finding]:
    file_label = str(trace_path)
    try:
        text = trace_path.read_text(encoding="utf-8")
    except OSError as e:
        return [Finding("front_matter", file_label, None, f"could not read file: {e}")]

    findings: list[Finding] = []
    try:
        data, fm_end = parse_front_matter(text)
    except FrontMatterError as e:
        return [Finding("front_matter", file_label, e.line, str(e),
                        hint="trace must begin with YAML front-matter delimited by '---'")]

    findings.extend(validate_front_matter(data, file_label))

    body_lines = text.splitlines()[fm_end:]
    body_start_line = fm_end + 1

    findings.extend(check_preamble(body_lines, body_start_line, file_label))

    sections = split_sections(body_lines, body_start_line)

    findings.extend(check_section_confidences(sections, file_label))
    findings.extend(check_high_citations(sections, file_label))
    findings.extend(check_overall_summary(body_lines, file_label))
    findings.extend(check_staleness_note(sections, data, file_label))

    if "input_type" in data and data["input_type"] in ALLOWED_INPUT_TYPE:
        findings.extend(check_required_sections(sections, data["input_type"], file_label))

    findings.extend(resolve_citations(sections, file_label, repo_roots))

    return findings


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("trace_path")
    parser.add_argument("--repo-root", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    trace_path = Path(args.trace_path).resolve()
    if not trace_path.is_file():
        print(f"error: {trace_path} is not a file", file=sys.stderr)
        return 2
    repo_roots = [Path(r).resolve() for r in args.repo_root]
    for rr in repo_roots:
        if not rr.is_dir():
            print(f"error: repo root {rr} is not a directory", file=sys.stderr)
            return 2

    findings = validate_trace(trace_path, repo_roots)

    if args.json:
        json.dump({
            "ok": len(findings) == 0,
            "findings_count": len(findings),
            "findings": [f.to_dict() for f in findings],
        }, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        if not findings:
            print(f"OK: {trace_path}")
        else:
            print(f"FAIL: {trace_path} — {len(findings)} finding(s)")
            print()
            for f in findings:
                print(f.format_human())
                print()

    return 0 if not findings else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
