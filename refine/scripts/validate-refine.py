#!/usr/bin/env python3
"""
validate-refine.py — Structural validator for /refine output artifacts.

Runs as the deterministic half of Phase 5 (the LLM validator handles the rest).
Stdlib-only.

Usage:
    python3 validate-refine.py <artifact_path> --input-type <type> [--json]

    <artifact_path>   Path to the refined-input .md file (or draft on disk).
    --input-type      question | bug | feature | refactor
                      If omitted, read from artifact front-matter.
    --json            Emit findings as JSON instead of human-readable text.

Exit codes:
    0   no findings
    1   findings present
    2   invocation/IO error

Finding categories:
    front_matter        Missing/invalid YAML front-matter
    schema              Front-matter field missing, wrong type, or invalid value
    preamble            Missing or malformed preamble line
    missing_section     Required section for input_type is absent
    dimension           Invalid dimension name, or dimension listed in both
                        addressed and assumed
    structural          refined_input identical to original_input (non-round-trip)
    round_trip          Round-trip artifact missing required '## Round-Trip' section
    hard_stop           hard_stop=true but '## How to Rephrase' section absent
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Schema constants — kept aligned with resources/refine-schema.json
# ---------------------------------------------------------------------------

ALLOWED_INPUT_TYPE = {"question", "bug", "feature", "refactor"}
ALLOWED_VERDICT    = {"PASS", "REVISE", "REVISED"}

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SEMVER_RE   = re.compile(r"^\d+\.\d+\.\d+(-[A-Za-z0-9.-]+)?$")
COMMIT_RE   = re.compile(r"^([0-9a-f]{7,40}|none)$")

REQUIRED_FRONT_MATTER = [
    "file", "original_input", "refined_input", "input_type", "created",
    "refine_skill_version", "dimensions_addressed", "dimensions_assumed",
    "clarifications", "validator_verdict",
]
OPTIONAL_FRONT_MATTER = ["context_commit", "hard_stop"]

# Canonical dimension names per input type — must match refine-schema.json
CANONICAL_DIMENSIONS: dict[str, list[str]] = {
    "question": [
        "scope_boundary",
        "audience_depth",
        "specific_subsystem",
    ],
    "bug": [
        "symptom_and_fixed_definition",
        "reproducer",
        "when_it_started",
        "frequency_and_conditions",
        "whats_already_been_tried",
    ],
    "feature": [
        "scope_boundary",
        "existing_pattern_preference",
        "migration_vs_greenfield",
        "cross_repo_scope",
        "performance_scale_targets",
        "user_visible_behavior",
    ],
    "refactor": [
        "tolerance_for_breaking_changes",
        "increment_size",
        "behavior_preservation",
        "trigger",
        "test_coverage_assumption",
        "out_of_scope",
    ],
}

# Required body sections per input type (matched by heading prefix)
REQUIRED_SECTIONS: dict[str, list[str]] = {
    "question":  ["Original Input", "Refined Input"],
    "bug":       ["Original Input", "Refined Input"],
    "feature":   ["Original Input", "Refined Input"],
    "refactor":  ["Original Input", "Refined Input"],
}

PREAMBLE_RE = re.compile(
    r"^\*\*Refined input:\*\*\s+.+\s+·\s+(question|bug|feature|refactor)\s+·\s+\d+\s+dimensions addressed,\s+\d+\s+assumed$"
)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")


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
# Front-matter parsing (stdlib YAML subset, same architecture as validate-trace.py)
# ---------------------------------------------------------------------------

class FrontMatterError(Exception):
    def __init__(self, message: str, line: int):
        super().__init__(message)
        self.line = line


def _unquote(s: str) -> str:
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    return s


def _indent_of(s: str) -> int:
    return len(s) - len(s.lstrip(" "))


def parse_front_matter(text: str) -> tuple[dict[str, Any], int]:
    """
    Parse YAML front-matter. Returns (data, end_line_1indexed).
    Supports: scalars, quoted scalars, simple sequences, simple nested mappings.
    Multi-line scalar values (block scalars with |/>) are NOT supported —
    the schema uses only flat scalars and lists.
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
        key   = k.strip()
        value = v.strip()
        my_indent = _indent_of(raw)

        if value == "":
            # Peek at next non-blank line to decide: sequence or nested mapping
            j = i + 1
            while j < end_idx and not lines[j].strip():
                j += 1

            if j >= end_idx or _indent_of(lines[j]) <= my_indent:
                data[key] = ""
                i += 1
                continue

            child_indent = _indent_of(lines[j])

            if lines[j].lstrip().startswith("- "):
                # Sequence
                seq: list[Any] = []
                while j < end_idx:
                    if not lines[j].strip():
                        j += 1
                        continue
                    if _indent_of(lines[j]) < child_indent:
                        break
                    if not (_indent_of(lines[j]) == child_indent and lines[j].lstrip().startswith("- ")):
                        break
                    item_text = lines[j].lstrip()[2:]
                    j += 1

                    # Collect continuation lines for this item (nested keys)
                    item_dict: dict[str, Any] | None = None
                    item_scalar: str | None = None

                    if ":" in item_text and not item_text.strip().startswith("#"):
                        ik, _, iv = item_text.partition(":")
                        item_dict = {ik.strip(): _unquote(iv.strip())}
                        # Collect further keys at deeper indent
                        while j < end_idx:
                            if not lines[j].strip():
                                j += 1
                                continue
                            if _indent_of(lines[j]) <= child_indent:
                                break
                            cont = lines[j].strip()
                            if ":" in cont:
                                ck, _, cv = cont.partition(":")
                                item_dict[ck.strip()] = _unquote(cv.strip())
                            j += 1
                    else:
                        item_scalar = _unquote(item_text.strip())

                    seq.append(item_dict if item_dict is not None else item_scalar)

                data[key] = seq
                i = j
                continue
            else:
                # Nested mapping
                nested: dict[str, Any] = {}
                while j < end_idx:
                    if not lines[j].strip():
                        j += 1
                        continue
                    if _indent_of(lines[j]) < child_indent:
                        break
                    inner = lines[j].strip()
                    if ":" not in inner:
                        raise FrontMatterError(
                            f"expected 'key: value' in nested map, got {inner!r}", j + 1
                        )
                    nk, _, nv = inner.partition(":")
                    nested[nk.strip()] = _unquote(nv.strip())
                    j += 1
                data[key] = nested
                i = j
                continue
        else:
            # Inline scalar — handle booleans and empty collections
            raw_val = _unquote(value)
            if raw_val.lower() == "true":
                data[key] = True
            elif raw_val.lower() == "false":
                data[key] = False
            elif raw_val == "[]":
                data[key] = []
            elif raw_val == "{}":
                data[key] = {}
            else:
                data[key] = raw_val
            i += 1

    return data, end_idx + 1


# ---------------------------------------------------------------------------
# Front-matter schema validation
# ---------------------------------------------------------------------------

def validate_front_matter(data: dict[str, Any], file: str) -> list[Finding]:
    findings: list[Finding] = []

    # Required fields
    for f in REQUIRED_FRONT_MATTER:
        if f not in data:
            findings.append(Finding(
                "schema", file, 1,
                f"required field missing: {f!r}",
                hint=f"add {f}: ... to front-matter",
            ))

    # Unknown fields
    allowed = set(REQUIRED_FRONT_MATTER) | set(OPTIONAL_FRONT_MATTER)
    for k in data:
        if k not in allowed:
            findings.append(Finding("schema", file, 1, f"unexpected field: {k!r}"))

    def check(name: str, fn, msg: str):
        if name in data and not fn(data[name]):
            findings.append(Finding(
                "schema", file, 1,
                f"{name!r}: {msg} (got {data[name]!r})",
            ))

    check("file",
          lambda v: isinstance(v, str) and v.startswith(".context/refinements/"),
          "must start with '.context/refinements/'")
    check("original_input",
          lambda v: isinstance(v, str) and len(v) > 0,
          "must be non-empty string")
    check("refined_input",
          lambda v: isinstance(v, str),
          "must be a string")
    check("input_type",
          lambda v: v in ALLOWED_INPUT_TYPE,
          f"must be one of {sorted(ALLOWED_INPUT_TYPE)}")
    check("created",
          lambda v: isinstance(v, str) and bool(ISO_DATE_RE.match(v)),
          "must be ISO date YYYY-MM-DD")
    check("refine_skill_version",
          lambda v: isinstance(v, str) and bool(SEMVER_RE.match(v)),
          "must be semver")
    check("validator_verdict",
          lambda v: v in ALLOWED_VERDICT,
          f"must be one of {sorted(ALLOWED_VERDICT)}")
    check("dimensions_addressed",
          lambda v: isinstance(v, list),
          "must be a list")
    check("dimensions_assumed",
          lambda v: isinstance(v, list),
          "must be a list")
    check("clarifications",
          lambda v: isinstance(v, list),
          "must be a list")

    # Validate clarification entries
    if "clarifications" in data and isinstance(data["clarifications"], list):
        for idx, c in enumerate(data["clarifications"]):
            if not isinstance(c, dict):
                findings.append(Finding(
                    "schema", file, 1,
                    f"clarifications[{idx}]: must be a mapping with 'dimension', 'question', 'answer'",
                ))
                continue
            for sub in ("dimension", "question", "answer"):
                if sub not in c:
                    findings.append(Finding(
                        "schema", file, 1,
                        f"clarifications[{idx}]: missing {sub!r}",
                    ))

    # Validate dimensions_assumed entries
    if "dimensions_assumed" in data and isinstance(data["dimensions_assumed"], list):
        for idx, a in enumerate(data["dimensions_assumed"]):
            if not isinstance(a, dict):
                findings.append(Finding(
                    "schema", file, 1,
                    f"dimensions_assumed[{idx}]: must be a mapping with 'dimension' and 'assumed_value'",
                ))
                continue
            for sub in ("dimension", "assumed_value"):
                if sub not in a:
                    findings.append(Finding(
                        "schema", file, 1,
                        f"dimensions_assumed[{idx}]: missing {sub!r}",
                    ))

    # context_commit entries
    if "context_commit" in data and isinstance(data["context_commit"], dict):
        for repo, entry in data["context_commit"].items():
            if not isinstance(entry, dict):
                findings.append(Finding(
                    "schema", file, 1,
                    f"context_commit[{repo!r}]: must be a mapping",
                ))
                continue
            for sub in ("context_commit", "head_commit"):
                if sub not in entry:
                    findings.append(Finding(
                        "schema", file, 1,
                        f"context_commit[{repo!r}]: missing {sub!r}",
                    ))
                elif not COMMIT_RE.match(str(entry[sub])):
                    findings.append(Finding(
                        "schema", file, 1,
                        f"context_commit[{repo!r}].{sub}: invalid commit hash",
                    ))

    return findings


# ---------------------------------------------------------------------------
# Dimension validation
# ---------------------------------------------------------------------------

def validate_dimensions(data: dict[str, Any], file: str) -> list[Finding]:
    findings: list[Finding] = []
    input_type = data.get("input_type")
    if input_type not in CANONICAL_DIMENSIONS:
        return findings  # already reported as schema error

    canonical = set(CANONICAL_DIMENSIONS[input_type])

    addressed: list[str] = []
    if isinstance(data.get("dimensions_addressed"), list):
        addressed = [d for d in data["dimensions_addressed"] if isinstance(d, str)]

    assumed_names: list[str] = []
    if isinstance(data.get("dimensions_assumed"), list):
        for entry in data["dimensions_assumed"]:
            if isinstance(entry, dict) and "dimension" in entry:
                assumed_names.append(entry["dimension"])

    # Check all addressed dimensions are canonical
    for d in addressed:
        if d not in canonical:
            findings.append(Finding(
                "dimension", file, None,
                f"dimensions_addressed contains unknown dimension {d!r} for input_type={input_type!r}",
                hint=f"valid dimensions: {sorted(canonical)}",
            ))

    # Check all assumed dimensions are canonical
    for d in assumed_names:
        if d not in canonical:
            findings.append(Finding(
                "dimension", file, None,
                f"dimensions_assumed contains unknown dimension {d!r} for input_type={input_type!r}",
                hint=f"valid dimensions: {sorted(canonical)}",
            ))

    # Check no dimension appears in both lists
    overlap = set(addressed) & set(assumed_names)
    for d in sorted(overlap):
        findings.append(Finding(
            "dimension", file, None,
            f"dimension {d!r} appears in both dimensions_addressed and dimensions_assumed",
            hint="a dimension can only be addressed OR assumed, not both",
        ))

    return findings


# ---------------------------------------------------------------------------
# Body checks
# ---------------------------------------------------------------------------

def extract_headings(body_lines: list[str], body_start_line: int) -> list[tuple[int, int, str]]:
    """Return list of (line_no, level, title)."""
    result = []
    for idx, line in enumerate(body_lines):
        m = HEADING_RE.match(line)
        if m:
            result.append((body_start_line + idx, len(m.group(1)), m.group(2).strip()))
    return result


def check_preamble(body_lines: list[str], body_start_line: int, file: str) -> list[Finding]:
    """Find the first non-blank, non-H1 line and verify the preamble pattern."""
    findings: list[Finding] = []
    found_h1 = False
    for idx, line in enumerate(body_lines):
        line_no = body_start_line + idx
        if not line.strip():
            continue
        if line.strip().startswith("# ") and not found_h1:
            found_h1 = True
            continue
        if not PREAMBLE_RE.match(line.strip()):
            findings.append(Finding(
                "preamble", file, line_no,
                "preamble line missing or malformed",
                hint="expected: '**Refined input:** <summary> · <type> · N dimensions addressed, M assumed'",
            ))
        return findings
    findings.append(Finding("preamble", file, None, "no preamble found in body"))
    return findings


def check_required_sections(
    headings: list[tuple[int, int, str]],
    input_type: str,
    data: dict[str, Any],
    file: str,
) -> list[Finding]:
    findings: list[Finding] = []
    titles = [t for _, _, t in headings]

    # All types need these two
    for req in REQUIRED_SECTIONS.get(input_type, []):
        if not any(req.lower() in t.lower() for t in titles):
            findings.append(Finding(
                "missing_section", file, None,
                f"required section {req!r} not found",
                hint=f"add a '## {req}' section to the artifact body",
            ))

    # Assumptions section required when dimensions_assumed is non-empty
    assumed = data.get("dimensions_assumed", [])
    if isinstance(assumed, list) and len(assumed) > 0:
        if not any("assumptions" in t.lower() for _, _, t in headings):
            findings.append(Finding(
                "missing_section", file, None,
                "'## Assumptions' section required when dimensions_assumed is non-empty",
            ))

    # Clarification log required when clarifications is non-empty
    clarifications = data.get("clarifications", [])
    if isinstance(clarifications, list) and len(clarifications) > 0:
        if not any("clarification" in t.lower() for _, _, t in headings):
            findings.append(Finding(
                "missing_section", file, None,
                "'## Clarification Log' section required when clarifications is non-empty",
            ))

    return findings


def check_hard_stop(
    headings: list[tuple[int, int, str]],
    data: dict[str, Any],
    file: str,
) -> list[Finding]:
    findings: list[Finding] = []
    is_hard_stop = data.get("hard_stop", False)
    if not is_hard_stop:
        return findings
    if not any("how to rephrase" in t.lower() for _, _, t in headings):
        findings.append(Finding(
            "hard_stop", file, None,
            "'## How to Rephrase' section required when hard_stop is true",
            hint="add a '## How to Rephrase' section with concrete guidance",
        ))
    return findings


def check_round_trip(
    body_lines: list[str],
    headings: list[tuple[int, int, str]],
    data: dict[str, Any],
    file: str,
) -> list[Finding]:
    """
    If original_input and refined_input are structurally identical (round-trip
    pass), a '## Round-Trip' section must be present explaining why.
    If they're different but look suspiciously similar, flag it as structural.
    """
    findings: list[Finding] = []
    is_hard_stop = data.get("hard_stop", False)
    if is_hard_stop:
        return findings  # hard-stop artifacts have empty refined_input by design

    original = data.get("original_input", "")
    refined  = data.get("refined_input", "")

    if not isinstance(original, str) or not isinstance(refined, str):
        return findings  # already caught by schema checks

    def normalize(s: str) -> str:
        return " ".join(s.lower().split())

    if normalize(original) == normalize(refined):
        # Round-trip pass — must have a Round-Trip section
        if not any("round-trip" in t.lower() or "round trip" in t.lower()
                   for _, _, t in headings):
            findings.append(Finding(
                "round_trip", file, None,
                "refined_input is identical to original_input but no '## Round-Trip' section is present",
                hint="add a '## Round-Trip' section noting this is a round-trip pass and why no changes were needed",
            ))
    elif len(refined) > 0 and len(original) > 0:
        # Different — verify refined is actually different enough to be useful
        # Heuristic: if refined is a strict substring of original with only whitespace differences, flag it
        if normalize(refined) in normalize(original) and len(normalize(refined)) / len(normalize(original)) > 0.95:
            findings.append(Finding(
                "structural", file, None,
                "refined_input appears to be nearly identical to original_input",
                hint="the refinement should differ structurally from the original; if this is a round-trip pass, add a '## Round-Trip' section",
            ))

    return findings


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def validate_artifact(
    artifact_path: Path,
    input_type_override: str | None,
) -> list[Finding]:
    file_label = str(artifact_path)

    try:
        text = artifact_path.read_text(encoding="utf-8")
    except OSError as e:
        return [Finding("front_matter", file_label, None, f"could not read file: {e}")]

    findings: list[Finding] = []

    try:
        data, fm_end = parse_front_matter(text)
    except FrontMatterError as e:
        return [Finding(
            "front_matter", file_label, e.line, str(e),
            hint="artifact must begin with YAML front-matter delimited by '---'",
        )]

    # Apply CLI override
    if input_type_override:
        if input_type_override not in ALLOWED_INPUT_TYPE:
            return [Finding(
                "front_matter", file_label, None,
                f"--input-type {input_type_override!r} is not valid; must be one of {sorted(ALLOWED_INPUT_TYPE)}",
            )]
        if "input_type" in data and data["input_type"] != input_type_override:
            findings.append(Finding(
                "schema", file_label, 1,
                f"--input-type override {input_type_override!r} differs from front-matter input_type {data['input_type']!r}",
                hint="either update the front-matter or remove the --input-type override",
            ))
        data["input_type"] = input_type_override

    findings.extend(validate_front_matter(data, file_label))
    findings.extend(validate_dimensions(data, file_label))

    body_lines = text.splitlines()[fm_end:]
    body_start_line = fm_end + 1

    findings.extend(check_preamble(body_lines, body_start_line, file_label))

    headings = extract_headings(body_lines, body_start_line)

    if "input_type" in data and data["input_type"] in ALLOWED_INPUT_TYPE:
        findings.extend(check_required_sections(headings, data["input_type"], data, file_label))

    findings.extend(check_hard_stop(headings, data, file_label))
    findings.extend(check_round_trip(body_lines, headings, data, file_label))

    return findings


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("artifact_path", help="Path to the refined-input .md artifact")
    parser.add_argument(
        "--input-type",
        choices=sorted(ALLOWED_INPUT_TYPE),
        help="Override input_type (uses front-matter value if omitted)",
    )
    parser.add_argument("--json", action="store_true", help="Emit findings as JSON")
    args = parser.parse_args(argv)

    artifact_path = Path(args.artifact_path).resolve()
    if not artifact_path.is_file():
        print(f"error: {artifact_path} is not a file", file=sys.stderr)
        return 2

    findings = validate_artifact(artifact_path, args.input_type)

    if args.json:
        json.dump(
            {
                "ok": len(findings) == 0,
                "findings_count": len(findings),
                "findings": [f.to_dict() for f in findings],
            },
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
    else:
        if not findings:
            print(f"OK: {artifact_path}")
        else:
            print(f"FAIL: {artifact_path} — {len(findings)} finding(s)")
            print()
            for f in findings:
                print(f.format_human())
                print()

    return 0 if not findings else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
