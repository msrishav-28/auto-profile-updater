"""
tests/test_write_readme.py - Unit test suite for write_readme.py marker manipulation.
"""

import os
import subprocess
import sys
import tempfile
import pytest

from write_readme import (
    BEGIN_MARKER,
    END_MARKER,
    MarkerError,
    extract_region,
    find_markers,
    replace_region,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
README_TEMPLATE = os.path.join(FIXTURES_DIR, "readme-template.md")
VALID_GENERATED = os.path.join(FIXTURES_DIR, "generated-valid.md")


def test_find_markers_valid():
    content = f"Header\n{BEGIN_MARKER}\nDynamic\n{END_MARKER}\nFooter\n"
    begin_idx, end_idx, prefix, suffix = find_markers(content)
    assert begin_idx == 1
    assert end_idx == 3
    assert prefix == f"Header\n{BEGIN_MARKER}\n"
    assert suffix == f"{END_MARKER}\nFooter\n"


def test_missing_begin_marker():
    content = f"Header\nDynamic\n{END_MARKER}\nFooter\n"
    with pytest.raises(MarkerError, match="Missing begin marker"):
        find_markers(content)


def test_missing_end_marker():
    content = f"Header\n{BEGIN_MARKER}\nDynamic\nFooter\n"
    with pytest.raises(MarkerError, match="Missing end marker"):
        find_markers(content)


def test_duplicate_begin_marker():
    content = f"{BEGIN_MARKER}\n{BEGIN_MARKER}\nDynamic\n{END_MARKER}\n"
    with pytest.raises(MarkerError, match="Duplicate begin markers"):
        find_markers(content)


def test_duplicate_end_marker():
    content = f"{BEGIN_MARKER}\nDynamic\n{END_MARKER}\n{END_MARKER}\n"
    with pytest.raises(MarkerError, match="Duplicate end markers"):
        find_markers(content)


def test_marker_order_inverted():
    content = f"{END_MARKER}\nDynamic\n{BEGIN_MARKER}\n"
    with pytest.raises(MarkerError, match="Invalid marker order"):
        find_markers(content)


def test_marker_not_on_own_line():
    content = f"Header {BEGIN_MARKER}\nDynamic\n{END_MARKER}\n"
    with pytest.raises(MarkerError, match="must appear on its own line"):
        find_markers(content)


def test_extract_region():
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as out_f:
        out_path = out_f.name

    try:
        extract_region(README_TEMPLATE, out_path)
        with open(out_path, "r", encoding="utf-8") as f:
            extracted = f.read()
        assert "## About Me" in extracted
        assert "## Current Focus" in extracted
        assert "## Recently Shipped" in extracted
        assert BEGIN_MARKER not in extracted
        assert END_MARKER not in extracted
    finally:
        if os.path.exists(out_path):
            os.remove(out_path)


def test_replace_region_preserves_static_bytes():
    with open(README_TEMPLATE, "r", encoding="utf-8") as f:
        original = f.read()

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as readme_f:
        readme_f.write(original)
        readme_path = readme_f.name

    try:
        replace_region(readme_path, VALID_GENERATED)
        with open(readme_path, "r", encoding="utf-8") as f:
            updated = f.read()

        # Check prefix matches original up to begin marker
        _, _, orig_prefix, orig_suffix = find_markers(original)
        _, _, upd_prefix, upd_suffix = find_markers(updated)

        assert orig_prefix == upd_prefix
        assert orig_suffix == upd_suffix
        assert updated.endswith("\n")

        # Verify new content is present
        with open(VALID_GENERATED, "r", encoding="utf-8") as gf:
            gen_text = gf.read().strip()
        assert gen_text in updated
    finally:
        if os.path.exists(readme_path):
            os.remove(readme_path)


def test_replace_rejects_content_with_markers():
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as readme_f:
        readme_f.write(f"Header\n{BEGIN_MARKER}\nDynamic\n{END_MARKER}\nFooter\n")
        readme_path = readme_f.name

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as gen_f:
        gen_f.write(f"Text containing {BEGIN_MARKER} sneakily")
        gen_path = gen_f.name

    try:
        with pytest.raises(MarkerError, match="forbidden AI marker strings"):
            replace_region(readme_path, gen_path)
    finally:
        if os.path.exists(readme_path):
            os.remove(readme_path)
        if os.path.exists(gen_path):
            os.remove(gen_path)


def test_cli_extract_and_replace():
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as out_f:
        out_path = out_f.name

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as readme_f:
        with open(README_TEMPLATE, "r", encoding="utf-8") as src:
            readme_f.write(src.read())
        readme_path = readme_f.name

    try:
        # CLI Extract
        res_ext = subprocess.run(
            [
                sys.executable,
                "write_readme.py",
                "--extract",
                "--readme",
                readme_path,
                "--output",
                out_path,
            ],
            capture_output=True,
            text=True,
        )
        assert res_ext.returncode == 0
        assert os.path.getsize(out_path) > 0

        # CLI Replace
        res_rep = subprocess.run(
            [
                sys.executable,
                "write_readme.py",
                "--readme",
                readme_path,
                "--generated",
                VALID_GENERATED,
            ],
            capture_output=True,
            text=True,
        )
        assert res_rep.returncode == 0
    finally:
        if os.path.exists(out_path):
            os.remove(out_path)
        if os.path.exists(readme_path):
            os.remove(readme_path)
