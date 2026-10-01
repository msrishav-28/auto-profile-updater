"""
tests/test_validate_generation.py - Unit test suite for validate_generation.py.
"""

import json
import os
import subprocess
import sys
import tempfile
import yaml
import pytest

from validate_generation import validate_candidate

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
FACTS_PATH = os.path.join(FIXTURES_DIR, "profile-facts.yml")
CONTEXT_PATH = os.path.join(FIXTURES_DIR, "context.json")
VALID_GEN_PATH = os.path.join(FIXTURES_DIR, "generated-valid.md")
INVALID_GEN_PATH = os.path.join(FIXTURES_DIR, "generated-invalid.md")


@pytest.fixture
def context_data():
    with open(CONTEXT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def facts_data():
    with open(FACTS_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture
def valid_text():
    with open(VALID_GEN_PATH, "r", encoding="utf-8") as f:
        return f.read()


def test_valid_fixture_passes(valid_text, context_data, facts_data):
    is_valid, report = validate_candidate(valid_text, context_data, facts_data)
    assert is_valid is True
    assert len(report["violations"]) == 0
    assert report["sections"]["about_me_words"] >= 45
    assert report["sections"]["about_me_words"] <= 75
    assert report["sections"]["current_focus_bullets"] == 3
    assert report["sections"]["recently_shipped_bullets"] == 2
    assert "forgebot" in report["mentioned_repositories"]
    assert "resume-analyzer" in report["mentioned_repositories"]


def test_missing_heading_fails(valid_text, context_data, facts_data):
    # Remove Recently Shipped heading
    broken = valid_text.replace("## Recently Shipped", "")
    is_valid, report = validate_candidate(broken, context_data, facts_data)
    assert is_valid is False
    codes = [v["code"] for v in report["violations"]]
    assert "HEADING_MISMATCH" in codes


def test_heading_order_fails(valid_text, context_data, facts_data):
    # Swap About Me and Current Focus
    broken = valid_text.replace("## About Me", "## TEMP").replace("## Current Focus", "## About Me").replace("## TEMP", "## Current Focus")
    is_valid, report = validate_candidate(broken, context_data, facts_data)
    assert is_valid is False
    codes = [v["code"] for v in report["violations"]]
    assert "HEADING_MISMATCH" in codes


def test_extra_heading_fails(valid_text, context_data, facts_data):
    broken = valid_text + "\n\n### Extra Section\n\nSome text."
    is_valid, report = validate_candidate(broken, context_data, facts_data)
    assert is_valid is False
    codes = [v["code"] for v in report["violations"]]
    assert "INVALID_HEADING_LEVEL" in codes or "HEADING_MISMATCH" in codes


def test_too_few_bullets_fails(valid_text, context_data, facts_data):
    # Leave only 1 bullet in Current Focus
    broken = valid_text.replace(
        "- Developing AI-enabled product concepts for practical user workflows\n", ""
    ).replace(
        "- Improving production engineering fundamentals across backend, frontend, deployment, and observability\n", ""
    )
    is_valid, report = validate_candidate(broken, context_data, facts_data)
    assert is_valid is False
    codes = [v["code"] for v in report["violations"]]
    assert "CURRENT_FOCUS_BULLET_COUNT" in codes


def test_bullet_word_limit_fails(valid_text, context_data, facts_data):
    # Bullet exceeding 22 words in Current Focus
    long_bullet = "- " + "word " * 25
    broken = valid_text.replace(
        "- Building agentic and automation-oriented developer tools",
        long_bullet.strip(),
    )
    is_valid, report = validate_candidate(broken, context_data, facts_data)
    assert is_valid is False
    codes = [v["code"] for v in report["violations"]]
    assert "CURRENT_FOCUS_BULLET_LENGTH" in codes


def test_prohibited_terms_detected(valid_text, context_data, facts_data):
    for term in ["ninja", "10x", "expert", "visionary", "passionate"]:
        candidate = valid_text + f" I am a {term} builder."
        is_valid, report = validate_candidate(candidate, context_data, facts_data)
        assert is_valid is False
        codes = [v["code"] for v in report["violations"]]
        assert "PROHIBITED_TERM" in codes


def test_emoji_detected(valid_text, context_data, facts_data):
    candidate = valid_text + " Great progress! 🚀"
    is_valid, report = validate_candidate(candidate, context_data, facts_data)
    assert is_valid is False
    codes = [v["code"] for v in report["violations"]]
    assert "EMOJI_DETECTED" in codes


def test_unapproved_organization_detected(valid_text, context_data, facts_data):
    candidate = valid_text.replace("Christ University", "Google")
    is_valid, report = validate_candidate(candidate, context_data, facts_data)
    assert is_valid is False
    codes = [v["code"] for v in report["violations"]]
    assert "UNAPPROVED_ORGANIZATION" in codes


def test_unapproved_repository_detected(valid_text, context_data, facts_data):
    candidate = valid_text.replace("forgebot", "unapproved-secret-project")
    is_valid, report = validate_candidate(candidate, context_data, facts_data)
    assert is_valid is False
    codes = [v["code"] for v in report["violations"]]
    assert "UNAPPROVED_REPOSITORY" in codes


def test_forbidden_constructs_detected(valid_text, context_data, facts_data):
    # Code fence
    c1 = valid_text + "\n```python\nprint(1)\n```"
    assert "FORBIDDEN_CODE_FENCE" in [v["code"] for v in validate_candidate(c1, context_data, facts_data)[1]["violations"]]

    # HTML
    c2 = valid_text + "\n<span>some html</span>"
    assert "FORBIDDEN_HTML" in [v["code"] for v in validate_candidate(c2, context_data, facts_data)[1]["violations"]]

    # Blockquote
    c3 = valid_text + "\n> Some quote"
    assert "FORBIDDEN_BLOCKQUOTE" in [v["code"] for v in validate_candidate(c3, context_data, facts_data)[1]["violations"]]

    # URL
    c4 = valid_text + "\nCheck https://example.com"
    assert "FORBIDDEN_URL" in [v["code"] for v in validate_candidate(c4, context_data, facts_data)[1]["violations"]]

    # AI marker
    c5 = valid_text + "\n<!-- AI:BEGIN -->"
    assert "FORBIDDEN_MARKER" in [v["code"] for v in validate_candidate(c5, context_data, facts_data)[1]["violations"]]


def test_secret_detection(valid_text, context_data, facts_data):
    candidate = valid_text + "\nToken: ghp_111111111111111111111111111111111111"
    is_valid, report = validate_candidate(candidate, context_data, facts_data)
    assert is_valid is False
    codes = [v["code"] for v in report["violations"]]
    assert "CREDENTIAL_DETECTED" in codes


def test_cli_execution():
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as rep_f:
        rep_path = rep_f.name

    try:
        # Valid execution returns 0
        res_valid = subprocess.run(
            [
                sys.executable,
                "validate_generation.py",
                "--generated",
                VALID_GEN_PATH,
                "--context",
                CONTEXT_PATH,
                "--facts",
                FACTS_PATH,
                "--report",
                rep_path,
            ],
            capture_output=True,
            text=True,
        )
        assert res_valid.returncode == 0
        with open(rep_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["valid"] is True

        # Invalid execution returns 1
        res_invalid = subprocess.run(
            [
                sys.executable,
                "validate_generation.py",
                "--generated",
                INVALID_GEN_PATH,
                "--context",
                CONTEXT_PATH,
                "--facts",
                FACTS_PATH,
                "--report",
                rep_path,
            ],
            capture_output=True,
            text=True,
        )
        assert res_invalid.returncode == 1
        with open(rep_path, "r", encoding="utf-8") as f:
            inv_data = json.load(f)
        assert inv_data["valid"] is False
        assert len(inv_data["violations"]) > 0

        # Missing input file returns 2
        res_missing = subprocess.run(
            [
                sys.executable,
                "validate_generation.py",
                "--generated",
                "nonexistent.md",
                "--context",
                CONTEXT_PATH,
                "--facts",
                FACTS_PATH,
                "--report",
                rep_path,
            ],
            capture_output=True,
            text=True,
        )
        assert res_missing.returncode == 2
    finally:
        if os.path.exists(rep_path):
            os.remove(rep_path)
