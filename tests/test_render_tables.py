"""
tests/test_render_tables.py - Unit test suite for render_tables.py.
"""

import json
import os
import tempfile
import yaml
import pytest

from render_tables import (
    find_regions,
    generate_top_languages_badges,
    generate_stack_trace_html,
    generate_current_focus_rows,
    generate_github_stats,
    generate_latest_posts,
    generate_active_builds_rows,
    process_readme,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
FACTS_PATH = os.path.join(FIXTURES_DIR, "profile-facts.yml")
CONTEXT_PATH = os.path.join(FIXTURES_DIR, "context.json")


@pytest.fixture
def context_data():
    with open(CONTEXT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def facts_data():
    with open(FACTS_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_find_regions_table_markers():
    content = """
<!-- TABLE:BEGIN:ACTIVE_BUILDS -->
| Project | Stack |
|---------|-------|
| test | python |
<!-- TABLE:END:ACTIVE_BUILDS -->
"""
    regions = find_regions(content)
    assert len(regions) == 1
    assert regions[0] == ("TABLE", "ACTIVE_BUILDS", 1, 5)


def test_find_regions_badge_markers():
    content = """
<!-- BADGES:BEGIN:TOP_LANGUAGES -->
python javascript
<!-- BADGES:END:TOP_LANGUAGES -->
"""
    regions = find_regions(content)
    assert len(regions) == 1
    assert regions[0] == ("BADGES", "TOP_LANGUAGES", 1, 3)


def test_find_regions_multiple_regions():
    content = """
<!-- TABLE:BEGIN:ACTIVE_BUILDS -->
old content
<!-- TABLE:END:ACTIVE_BUILDS -->

<!-- BADGES:BEGIN:TOP_LANGUAGES -->
old badges
<!-- BADGES:END:TOP_LANGUAGES -->
"""
    regions = find_regions(content)
    assert len(regions) == 2
    assert regions[0] == ("TABLE", "ACTIVE_BUILDS", 1, 3)
    assert regions[1] == ("BADGES", "TOP_LANGUAGES", 5, 7)


def test_find_regions_no_markers():
    content = "Just some text without markers"
    regions = find_regions(content)
    assert len(regions) == 0


def test_find_regions_mismatched_markers():
    content = """
<!-- TABLE:BEGIN:ACTIVE_BUILDS -->
content only
"""
    regions = find_regions(content)
    assert len(regions) == 0


def test_generate_top_languages_badges(context_data):
    badges = generate_top_languages_badges(context_data)
    assert isinstance(badges, list)
    # Check that badges are generated as markdown images
    if badges:
        assert all("![Python]" in b or "![JavaScript]" in b or "![TypeScript]" in b for b in badges)


def test_generate_top_languages_badges_empty_context():
    badges = generate_top_languages_badges({"repositories": []})
    assert badges == []


def test_generate_stack_trace_html(context_data):
    html = generate_stack_trace_html(context_data)
    assert isinstance(html, list)
    assert "<table>" in html[0]
    assert "</table>" in html[-1]
    # Check for table structure
    assert any("<th align=\"left\">Layer</th>" in line for line in html)
    assert any("<th align=\"left\">Worked with</th>" in line for line in html)


def test_generate_stack_trace_html_empty_context():
    html = generate_stack_trace_html({"repositories": []})
    assert html == []


def test_generate_current_focus_rows(facts_data):
    rows = generate_current_focus_rows(facts_data)
    assert isinstance(rows, list)
    assert len(rows) > 0
    # Check that rows are markdown table rows
    assert all(row.startswith("|") and row.endswith("|") for row in rows)


def test_generate_current_focus_rows_empty_facts():
    rows = generate_current_focus_rows({"manual_current_focus": []})
    assert len(rows) == 1
    assert "No current focus specified" in rows[0]


def test_generate_github_stats(context_data):
    rows = generate_github_stats(context_data)
    assert isinstance(rows, list)
    assert len(rows) > 0
    # Check for expected table rows
    assert any("Total Public Repositories" in row for row in rows)
    assert any("Total Stars Earned" in row for row in rows)


def test_generate_github_stats_empty_context():
    rows = generate_github_stats({"repositories": []})
    assert len(rows) == 2
    assert any("Total Public Repositories | 0" in row for row in rows)
    assert any("Total Stars Earned | 0" in row for row in rows)


def test_generate_latest_posts(facts_data):
    rows = generate_latest_posts(facts_data)
    assert isinstance(rows, list)
    # Should return placeholder since no RSS URL is configured
    assert len(rows) == 1
    assert "No RSS feed configured" in rows[0] or "Blog support enabled" in rows[0]


def test_generate_latest_posts_with_rss():
    rows = generate_latest_posts({"blog_rss_url": "https://example.com/rss"})
    assert len(rows) == 1
    assert "Blog support enabled" in rows[0]
    assert "https://example.com/rss" in rows[0]


def test_generate_active_builds_rows(context_data, facts_data):
    rows = generate_active_builds_rows(context_data, facts_data)
    assert isinstance(rows, list)
    # Check that rows are markdown table rows with 5 columns
    if rows:
        # Skip the "No public repositories" case
        if not any("No public repositories" in row for row in rows):
            assert all(row.count("|") >= 5 for row in rows)


def test_generate_active_builds_rows_empty_context():
    rows = generate_active_builds_rows({"repositories": []}, {"featured_repositories": []})
    assert len(rows) == 1
    assert "No public repositories" in rows[0]


def test_process_readme_integration(context_data, facts_data):
    """Integration test for the full process_readme function."""
    readme_content = """
# Test README

<!-- TABLE:BEGIN:ACTIVE_BUILDS -->
| Project | What it does | Stack | Status | Link |
|---------|--------------|-------|--------|------|
| old | old desc | old stack | old status | old link |
<!-- TABLE:END:ACTIVE_BUILDS -->

<!-- TABLE:BEGIN:CURRENT_FOCUS -->
| Focus | Status |
|-------|--------|
| old focus | old status |
<!-- TABLE:END:CURRENT_FOCUS -->

<!-- BADGES:BEGIN:TOP_LANGUAGES -->
old badges
<!-- BADGES:END:TOP_LANGUAGES -->
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as readme_file:
        readme_file.write(readme_content)
        readme_path = readme_file.name

    try:
        process_readme(readme_path, CONTEXT_PATH, FACTS_PATH)

        with open(readme_path, 'r', encoding='utf-8') as f:
            updated_content = f.read()

        # Verify that markers are preserved
        assert "<!-- TABLE:BEGIN:ACTIVE_BUILDS -->" in updated_content
        assert "<!-- TABLE:END:ACTIVE_BUILDS -->" in updated_content
        assert "<!-- TABLE:BEGIN:CURRENT_FOCUS -->" in updated_content
        assert "<!-- TABLE:END:CURRENT_FOCUS -->" in updated_content
        assert "<!-- BADGES:BEGIN:TOP_LANGUAGES -->" in updated_content
        assert "<!-- BADGES:END:TOP_LANGUAGES -->" in updated_content

        # Verify that old content was replaced
        assert "old desc" not in updated_content
        assert "old focus" not in updated_content
        assert "old badges" not in updated_content

    finally:
        os.unlink(readme_path)


def test_process_readme_no_markers(context_data, facts_data):
    """Test that process_readme handles READMEs without markers gracefully."""
    readme_content = "# Test README\n\nJust some content without markers."

    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as readme_file:
        readme_file.write(readme_content)
        readme_path = readme_file.name

    try:
        process_readme(readme_path, CONTEXT_PATH, FACTS_PATH)

        with open(readme_path, 'r', encoding='utf-8') as f:
            updated_content = f.read()

        # Content should remain unchanged
        assert updated_content == readme_content

    finally:
        os.unlink(readme_path)
