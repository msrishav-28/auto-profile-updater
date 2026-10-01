#!/usr/bin/env python3
"""
validate_generation.py - Independent deterministic validator for AI profile generation.

Enforces structural, policy, and evidence invariants before any candidate text
can be spliced into the public README or submitted as a pull request.
"""

import argparse
import datetime
import json
import os
import re
import sys
import unicodedata
from typing import Any

import yaml


class ConfigError(Exception):
    """Raised when source facts or context configuration is invalid."""
    pass


PROHIBITED_TERMS_DEFAULT = [
    "expert",
    "world-class",
    "revolutionary",
    "cutting-edge",
    "10x",
    "ninja",
    "guru",
    "visionary",
    "passionate",
    "best-in-class",
]

HYPE_PHRASES = [
    "industry-leading",
    "award-winning",
    "millions of users",
    "production-grade",
    "deployed globally",
]

KNOWN_ORG_PATTERNS = [
    r"\bGoogle\b",
    r"\bMicrosoft\b",
    r"\bAmazon\b",
    r"\bMeta\b",
    r"\bApple\b",
    r"\bNetflix\b",
    r"\bISRO\b",
    r"\bOpenAI\b",
    r"\bAnthropic\b",
    r"\bIIT\b",
    r"\bNIT\b",
    r"\bStanford\b",
    r"\bMIT\b",
    r"\bHarvard\b",
]

SECRET_PATTERNS = [
    (r"ghp_[0-9a-zA-Z]{36}", "GitHub Personal Access Token"),
    (r"github_pat_[0-9a-zA-Z_]{22,}", "Fine-Grained GitHub Token"),
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "Private Key Header"),
    (r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{25,}", "Bearer Token"),
    (r"\b[0-9a-fA-F]{40}\b", "40-character hex secret / commit SHA token"),
]


def is_emoji(char: str) -> bool:
    """Check if character is an emoji or decorative symbol."""
    cp = ord(char)
    # Common emoji Unicode code-point blocks
    if (
        0x1F600 <= cp <= 0x1F64F  # Emoticons
        or 0x1F300 <= cp <= 0x1F5FF  # Misc Symbols and Pictographs
        or 0x1F680 <= cp <= 0x1F6FF  # Transport and Map
        or 0x1F1E0 <= cp <= 0x1F1FF  # Regional indicator symbols (Flags)
        or 0x2600 <= cp <= 0x26FF  # Misc symbols
        or 0x2700 <= cp <= 0x27BF  # Dingbats
        or 0xFE00 <= cp <= 0xFE0F  # Variation Selectors
        or 0x1F900 <= cp <= 0x1F9FF  # Supplemental Symbols and Pictographs
        or 0x1FA00 <= cp <= 0x1FA6F  # Chess / Symbols Extended-A
        or 0x1FA70 <= cp <= 0x1FAFF  # Symbols and Pictographs Extended-A
        or cp == 0x200D  # Zero-width joiner
    ):
        return True

    category = unicodedata.category(char)
    return category in ("So", "Sk")


def count_words(text: str) -> int:
    """Returns number of whitespace-delimited words."""
    return len(text.split())


def validate_candidate(
    generated_text: str,
    context: dict[str, Any],
    facts: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    """
    Validates generated candidate markdown against structural, policy, and evidence rules.

    Returns:
        (is_valid, report_dict)
    """
    violations: list[dict[str, str]] = []
    mentioned_repos: set[str] = set()
    mentioned_orgs: set[str] = set()

    total_words = count_words(generated_text)

    # 1. Structural Checks
    lines = generated_text.splitlines()

    # Markdown forbidden constructs
    if "```" in generated_text:
        violations.append({
            "code": "FORBIDDEN_CODE_FENCE",
            "message": "Candidate contains forbidden markdown code fences.",
        })

    if re.search(r"<[^>]+>", generated_text):
        violations.append({
            "code": "FORBIDDEN_HTML",
            "message": "Candidate contains forbidden HTML tags.",
        })

    if "<!-- AI:" in generated_text:
        violations.append({
            "code": "FORBIDDEN_MARKER",
            "message": "Candidate contains forbidden AI marker strings.",
        })

    if re.search(r"\|\s*[-:]+[-|\s:]*\|", generated_text):
        violations.append({
            "code": "FORBIDDEN_TABLE",
            "message": "Candidate contains forbidden table separator lines.",
        })

    if any(line.strip().startswith(">") for line in lines):
        violations.append({
            "code": "FORBIDDEN_BLOCKQUOTE",
            "message": "Candidate contains forbidden markdown blockquotes.",
        })

    if re.search(r"https?://", generated_text):
        violations.append({
            "code": "FORBIDDEN_URL",
            "message": "Candidate contains forbidden URL strings.",
        })

    # Headings verification
    heading_lines = [line.strip() for line in lines if line.strip().startswith("#")]
    expected_headings = ["## About Me", "## Current Focus", "## Recently Shipped"]

    if heading_lines != expected_headings:
        if any(not h.startswith("## ") for h in heading_lines):
            violations.append({
                "code": "INVALID_HEADING_LEVEL",
                "message": f"All headings must be '##' level. Found: {heading_lines}",
            })
        if heading_lines != expected_headings:
            violations.append({
                "code": "HEADING_MISMATCH",
                "message": (
                    f"Headings must be exactly {expected_headings} in order. "
                    f"Found: {heading_lines}"
                ),
            })

    # Parse sections
    sections: dict[str, list[str]] = {
        "About Me": [],
        "Current Focus": [],
        "Recently Shipped": [],
    }
    current_section = None

    for line in lines:
        stripped = line.strip()
        if stripped in expected_headings:
            current_section = stripped.replace("## ", "")
            continue
        if current_section and stripped:
            sections[current_section].append(stripped)

    # Validate About Me section
    about_me_text = " ".join(sections["About Me"])
    about_me_words = count_words(about_me_text)

    # Must be 1 paragraph (no bullet points)
    if any(line.startswith(("-", "*", "1.", "2.")) for line in sections["About Me"]):
        violations.append({
            "code": "ABOUT_ME_NOT_PARAGRAPH",
            "message": "About Me section must be a narrative paragraph without bullets.",
        })

    if about_me_words < 45 or about_me_words > 75:
        violations.append({
            "code": "ABOUT_ME_WORD_COUNT",
            "message": f"About Me paragraph contains {about_me_words} words; required is 45-75.",
        })

    # Validate Current Focus section
    current_focus_lines = sections["Current Focus"]
    cf_bullets = [l for l in current_focus_lines if l.startswith(("- ", "* "))]

    # Check for nested bullets (indented bullet lines)
    if any(line.startswith(("  -", "  *", "\t-", "\t*")) for line in lines):
        violations.append({
            "code": "NESTED_BULLETS_FORBIDDEN",
            "message": "Nested bullets are forbidden.",
        })

    if len(cf_bullets) < 3 or len(cf_bullets) > 5:
        violations.append({
            "code": "CURRENT_FOCUS_BULLET_COUNT",
            "message": (
                f"Current Focus contains {len(cf_bullets)} bullets; required is 3-5."
            ),
        })

    for i, b in enumerate(cf_bullets):
        b_content = re.sub(r"^[-*]\s+", "", b).strip()
        w_count = count_words(b_content)
        if w_count > 22:
            violations.append({
                "code": "CURRENT_FOCUS_BULLET_LENGTH",
                "message": (
                    f"Current Focus bullet {i + 1} contains {w_count} words; maximum is 22."
                ),
            })

    # Validate Recently Shipped section
    recently_shipped_lines = sections["Recently Shipped"]
    rs_bullets = [l for l in recently_shipped_lines if l.startswith(("- ", "* "))]

    if len(rs_bullets) < 2 or len(rs_bullets) > 5:
        violations.append({
            "code": "RECENTLY_SHIPPED_BULLET_COUNT",
            "message": (
                f"Recently Shipped contains {len(rs_bullets)} bullets; required is 2-5."
            ),
        })

    for i, b in enumerate(rs_bullets):
        b_content = re.sub(r"^[-*]\s+", "", b).strip()
        w_count = count_words(b_content)
        if w_count > 26:
            violations.append({
                "code": "RECENTLY_SHIPPED_BULLET_LENGTH",
                "message": (
                    f"Recently Shipped bullet {i + 1} contains {w_count} words; maximum is 26."
                ),
            })

    # Total word count: 80–220
    if total_words < 80 or total_words > 220:
        violations.append({
            "code": "TOTAL_WORD_COUNT",
            "message": f"Output contains {total_words} words; required is 80-220.",
        })

    # 2. Policy Checks: Prohibited Terms
    prohibited_terms = set(PROHIBITED_TERMS_DEFAULT)
    writing_config = facts.get("writing", {})
    if "prohibited_terms" in writing_config:
        prohibited_terms.update(writing_config["prohibited_terms"])

    for term in prohibited_terms:
        # Case-insensitive whole-word match
        pattern = r"\b" + re.escape(term) + r"\b"
        if re.search(pattern, generated_text, re.IGNORECASE):
            violations.append({
                "code": "PROHIBITED_TERM",
                "message": f"Candidate contains prohibited term: {term!r}",
            })

    # Policy Checks: Hype Phrases
    for phrase in HYPE_PHRASES:
        if re.search(r"\b" + re.escape(phrase) + r"\b", generated_text, re.IGNORECASE):
            violations.append({
                "code": "PROHIBITED_HYPE_PHRASE",
                "message": f"Candidate contains unapproved hype phrase: {phrase!r}",
            })

    # Policy Checks: Emojis
    emoji_chars = [c for c in generated_text if is_emoji(c)]
    if emoji_chars:
        unique_emojis = sorted(list(set(emoji_chars)))
        emoji_desc = [f"U+{ord(c):04X}" for c in unique_emojis]
        violations.append({
            "code": "EMOJI_DETECTED",
            "message": f"Candidate contains forbidden emoji/symbols: {emoji_desc}",
        })

    # Policy Checks: Secret Patterns
    for pattern, name in SECRET_PATTERNS:
        if re.search(pattern, generated_text):
            violations.append({
                "code": "CREDENTIAL_DETECTED",
                "message": f"Candidate matches credential pattern: {name}",
            })

    # 3. Evidence Checks: Organizations
    allowed_orgs = set()
    # From facts writing.allowed_organizations
    allowed_orgs.update(writing_config.get("allowed_organizations", []))
    # From top-level allowed_organizations if present
    allowed_orgs.update(facts.get("allowed_organizations", []))
    # From approved_experience
    for exp in facts.get("approved_experience", []):
        if isinstance(exp, dict) and "name" in exp:
            allowed_orgs.add(exp["name"])

    # Detect known unapproved organizations
    for org_pattern in KNOWN_ORG_PATTERNS:
        matches = re.findall(org_pattern, generated_text)
        for match in matches:
            if match not in allowed_orgs:
                mentioned_orgs.add(match)
                violations.append({
                    "code": "UNAPPROVED_ORGANIZATION",
                    "message": f"Mentioned unapproved organization: {match!r}",
                })

    for org in allowed_orgs:
        if re.search(r"\b" + re.escape(org) + r"\b", generated_text, re.IGNORECASE):
            mentioned_orgs.add(org)

    # 4. Evidence Checks: Repositories
    allowed_repos = set(context.get("allowed_repositories", []))
    for r in context.get("repositories", []):
        if isinstance(r, dict) and "name" in r:
            allowed_repos.add(r["name"])
    # Also add featured_repositories from facts
    allowed_repos.update(facts.get("featured_repositories", []))

    # Extract repo mentions: backticked strings, or leading repo names in bullets like "repo: desc" or "`repo`"
    backticked = re.findall(r"`([a-zA-Z0-9_\-\.]+)`", generated_text)
    for b_item in backticked:
        if b_item in allowed_repos:
            mentioned_repos.add(b_item)
        elif re.match(r"^[a-zA-Z0-9_\-]+$", b_item) and len(b_item) > 3:
            # Check if this looks like an attempted repo mention
            violations.append({
                "code": "UNAPPROVED_REPOSITORY",
                "message": f"Backticked repository {b_item!r} is not in allowed repositories.",
            })

    # Check bullet prefixes in Recently Shipped for repo names
    for b in rs_bullets:
        clean_b = re.sub(r"^[-*]\s+", "", b).strip()
        prefix_match = re.match(r"^`?([a-zA-Z0-9_\-]+)`?\s*[:\-–—]", clean_b)
        if prefix_match:
            repo_candidate = prefix_match.group(1)
            if repo_candidate in allowed_repos:
                mentioned_repos.add(repo_candidate)
            else:
                violations.append({
                    "code": "UNAPPROVED_REPOSITORY",
                    "message": f"Referenced repository {repo_candidate!r} is not in allowed repositories.",
                })

    is_valid = len(violations) == 0

    report = {
        "valid": is_valid,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "word_count": total_words,
        "sections": {
            "about_me_words": about_me_words,
            "current_focus_bullets": len(cf_bullets),
            "recently_shipped_bullets": len(rs_bullets),
        },
        "mentioned_repositories": sorted(list(mentioned_repos)),
        "mentioned_organizations": sorted(list(mentioned_orgs)),
        "violations": violations,
    }

    return is_valid, report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Validate generated README markdown candidate against structural, policy, and evidence invariants."
    )
    parser.add_argument("--generated", required=True, help="Path to generated markdown candidate")
    parser.add_argument("--context", required=True, help="Path to context.json")
    parser.add_argument("--facts", required=True, help="Path to profile-facts.yml")
    parser.add_argument("--report", required=True, help="Path to write validation-report.json")

    args = parser.parse_args()

    # Exit code 2: CLI error or unreadable source file
    for path, desc in [
        (args.generated, "Generated markdown"),
        (args.context, "Context JSON"),
        (args.facts, "Profile facts YAML"),
    ]:
        if not os.path.isfile(path):
            print(f"Error (Exit 2): {desc} file not found: {path}", file=sys.stderr)
            return 2

    # Exit code 3: Invalid source configuration / schema
    try:
        with open(args.generated, "r", encoding="utf-8") as f:
            generated_text = f.read()

        with open(args.context, "r", encoding="utf-8") as f:
            context = json.load(f)

        with open(args.facts, "r", encoding="utf-8") as f:
            facts = yaml.safe_load(f)

        if not isinstance(context, dict) or not isinstance(facts, dict):
            raise ConfigError("context.json and profile-facts.yml must be JSON/YAML mappings.")
    except Exception as err:
        print(f"Configuration Error (Exit 3): Failed to parse configuration: {err}", file=sys.stderr)
        return 3

    try:
        is_valid, report = validate_candidate(generated_text, context, facts)

        os.makedirs(os.path.dirname(os.path.abspath(args.report)), exist_ok=True)
        with open(args.report, "w", encoding="utf-8", newline="\n") as f:
            json.dump(report, f, indent=2)

        if is_valid:
            print("Validation PASSED: Candidate complies with all rules.")
            return 0
        else:
            print(f"Validation FAILED: {len(report['violations'])} violation(s) found.")
            for v in report["violations"]:
                print(f"  [{v['code']}] {v['message']}")
            return 1
    except Exception as err:
        print(f"Unexpected Error: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
