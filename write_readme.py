#!/usr/bin/env python3
"""
write_readme.py - Precision marker-based README extraction and splicing.

Operates exclusively between:
<!-- AI:BEGIN -->
and
<!-- AI:END -->
"""

import argparse
import os
import re
import sys

BEGIN_MARKER = "<!-- AI:BEGIN -->"
END_MARKER = "<!-- AI:END -->"


class MarkerError(Exception):
    """Raised when marker invariants are violated."""
    pass


def find_markers(content: str) -> tuple[int, int, str, str]:
    """
    Locates the marker lines and validates marker invariants.

    Returns:
        (begin_idx, end_idx, prefix, suffix)
    Raises:
        MarkerError if invariants are violated.
    """
    lines = content.splitlines(keepends=True)
    begin_matches = []
    end_matches = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if BEGIN_MARKER in stripped:
            if stripped != BEGIN_MARKER:
                raise MarkerError(
                    f"Line {i + 1}: Begin marker must appear on its own line: {line.strip()!r}"
                )
            begin_matches.append(i)
        elif END_MARKER in stripped:
            if stripped != END_MARKER:
                raise MarkerError(
                    f"Line {i + 1}: End marker must appear on its own line: {line.strip()!r}"
                )
            end_matches.append(i)

    if len(begin_matches) == 0:
        raise MarkerError("Missing begin marker: <!-- AI:BEGIN -->")
    if len(begin_matches) > 1:
        raise MarkerError(f"Duplicate begin markers found ({len(begin_matches)} occurrences)")

    if len(end_matches) == 0:
        raise MarkerError("Missing end marker: <!-- AI:END -->")
    if len(end_matches) > 1:
        raise MarkerError(f"Duplicate end markers found ({len(end_matches)} occurrences)")

    begin_idx = begin_matches[0]
    end_idx = end_matches[0]

    if end_idx <= begin_idx:
        raise MarkerError(
            f"Invalid marker order: end marker (line {end_idx + 1}) appears before begin marker (line {begin_idx + 1})"
        )

    # Prefix includes everything up to and including the begin marker line
    prefix = "".join(lines[: begin_idx + 1])
    # Suffix includes end marker line and everything after it
    suffix = "".join(lines[end_idx:])

    return begin_idx, end_idx, prefix, suffix


def extract_region(readme_path: str, output_path: str) -> None:
    """Extracts content between markers to output_path."""
    if not os.path.isfile(readme_path):
        raise FileNotFoundError(f"README file not found: {readme_path}")

    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.splitlines(keepends=True)
    begin_idx, end_idx, _, _ = find_markers(content)

    region_lines = lines[begin_idx + 1 : end_idx]
    region_text = "".join(region_lines).strip()

    # Ensure parent directory exists
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(region_text + ("\n" if region_text else ""))


def replace_region(readme_path: str, generated_path: str) -> None:
    """Replaces content between markers with content from generated_path."""
    if not os.path.isfile(readme_path):
        raise FileNotFoundError(f"README file not found: {readme_path}")
    if not os.path.isfile(generated_path):
        raise FileNotFoundError(f"Generated content file not found: {generated_path}")

    with open(readme_path, "r", encoding="utf-8") as f:
        readme_content = f.read()

    with open(generated_path, "r", encoding="utf-8") as f:
        generated_content = f.read()

    # Invariant: Generated content must never include marker strings
    if BEGIN_MARKER in generated_content or END_MARKER in generated_content or "<!-- AI:" in generated_content:
        raise MarkerError("Generated content contains forbidden AI marker strings")

    _, _, prefix, suffix = find_markers(readme_content)

    clean_generated = generated_content.strip()

    # Normalize prefix to end with a single newline after marker
    if not prefix.endswith("\n"):
        prefix += "\n"

    # Normalize suffix: ensure newline at end if original had one
    # The formatted insertion will be: prefix + "\n" + clean_generated + "\n\n" + suffix
    new_readme = f"{prefix}\n{clean_generated}\n\n{suffix}"

    # Retain final newline at end of README
    if not new_readme.endswith("\n"):
        new_readme += "\n"

    with open(readme_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_readme)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Extract or replace the marker-bounded dynamic region of a README."
    )
    parser.add_argument(
        "--extract",
        action="store_true",
        help="Extract the dynamic region to --output",
    )
    parser.add_argument(
        "--readme",
        required=True,
        help="Path to README.md",
    )
    parser.add_argument(
        "--output",
        help="Output path for extracted dynamic region (used with --extract)",
    )
    parser.add_argument(
        "--generated",
        help="Path to generated markdown file (used for replacement)",
    )

    args = parser.parse_args()

    try:
        if args.extract:
            if not args.output:
                parser.error("--extract requires --output")
            extract_region(args.readme, args.output)
            print(f"Extracted dynamic region to {args.output}")
        else:
            if not args.generated:
                parser.error("Replacement mode requires --generated")
            replace_region(args.readme, args.generated)
            print(f"Successfully updated dynamic region in {args.readme}")
        return 0
    except (MarkerError, FileNotFoundError, ValueError) as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
    except Exception as err:
        print(f"Unexpected error: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
