#!/usr/bin/env python3
"""
collect_context.py - Collects, scores, and sanitizes public GitHub signals.

Gathers public repository evidence via GitHub GraphQL API, applies deterministic
scoring, sanitizes untrusted text (including prompt-injection mitigations),
and produces structured context.json and compact context.md.
"""

import argparse
import datetime
import json
import os
import re
import sys
from typing import Any

import requests
import yaml

GRAPHQL_QUERY = """
query ProfileContext($login: String!, $repoLimit: Int!) {
  user(login: $login) {
    login
    name
    bio
    location
    followers { totalCount }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalRepositoryContributions
    }
    repositories(
      first: $repoLimit
      ownerAffiliations: OWNER
      orderBy: { field: PUSHED_AT, direction: DESC }
    ) {
      nodes {
        name
        nameWithOwner
        url
        homepageUrl
        description
        isPrivate
        isArchived
        isFork
        pushedAt
        createdAt
        updatedAt
        stargazerCount
        forkCount
        primaryLanguage { name }
        repositoryTopics(first: 10) {
          nodes { topic { name } }
        }
        releases(first: 3, orderBy: { field: CREATED_AT, direction: DESC }) {
          nodes { name tagName publishedAt url }
        }
        defaultBranchRef {
          name
          target {
            ... on Commit {
              history(first: 5) {
                nodes { committedDate messageHeadline url }
              }
            }
          }
        }
      }
    }
  }
}
"""

PROMPT_INJECTION_PHRASES = [
    r"ignore\s+all\s+previous\s+instructions",
    r"ignore\s+previous\s+instructions",
    r"system\s+prompt",
    r"developer\s+message",
    r"assistant\s+message",
    r"you\s+are\s+chatgpt",
    r"do\s+not\s+follow",
    r"jailbreak",
    r"reveal\s+secrets",
]

SECRET_PATTERNS = [
    r"ghp_[0-9a-zA-Z]{36}",
    r"github_pat_[0-9a-zA-Z_]{22,}",
    r"AKIA[0-9A-Z]{16}",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{25,}",
]


def sanitize_text(text: str | None, max_length: int = 400, strip_urls: bool = True) -> str:
    """Sanitizes untrusted text strings from GitHub API."""
    if not text:
        return ""

    # Remove control characters (except newline and tab)
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Normalize whitespace
    sanitized = re.sub(r"\s+", " ", sanitized).strip()

    # Redact prompt-injection phrases
    for pattern in PROMPT_INJECTION_PHRASES:
        sanitized = re.sub(pattern, "[REDACTED]", sanitized, flags=re.IGNORECASE)

    # Redact secret patterns
    for pattern in SECRET_PATTERNS:
        sanitized = re.sub(pattern, "[REDACTED_SECRET]", sanitized)

    # Strip URLs if requested (excluding github repo references)
    if strip_urls:
        sanitized = re.sub(r"https?://\S+", "", sanitized)
        sanitized = re.sub(r"\s+", " ", sanitized).strip()

    # Truncate
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip() + "..."

    return sanitized


def parse_iso_date(date_str: str | None) -> datetime.datetime | None:
    """Parses ISO timestamp string to UTC datetime."""
    if not date_str:
        return None
    try:
        # Handle trailing Z
        clean_str = date_str.replace("Z", "+00:00")
        return datetime.datetime.fromisoformat(clean_str)
    except Exception:
        return None


def calculate_repo_score(
    repo: dict[str, Any],
    featured_repos: list[str],
    privacy_config: dict[str, Any] | None = None,
    now: datetime.datetime | None = None,
) -> int:
    """
    Calculates deterministic repository score based on specification rules.
    """
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)

    name = repo.get("name", "")
    is_featured = name in featured_repos
    is_fork = repo.get("isFork", False)
    is_archived = repo.get("isArchived", False)
    is_private = repo.get("isPrivate", False)

    # Exclusions
    if is_archived:
        return -1
    if is_fork and not is_featured:
        return -1

    # Privacy filtering
    if is_private:
        if not privacy_config or not privacy_config.get("include_private", False):
            return -1
        allowed_private = privacy_config.get("allowed_private_repositories", [])
        if allowed_private and name not in allowed_private and not is_featured:
            return -1

    score = 0

    # 1. Featured bonus (+100)
    if is_featured:
        score += 100

    # 2. Public original repository (+20)
    if not is_fork:
        score += 20

    # 3. Meaningful description (+10)
    desc = repo.get("description") or ""
    if len(desc.strip()) > 5:
        score += 10

    # 4. One or more topics (+5)
    topics_nodes = repo.get("repositoryTopics", {}).get("nodes", [])
    if len(topics_nodes) > 0:
        score += 5

    # 5. Release within 180 days (+10)
    releases_nodes = repo.get("releases", {}).get("nodes", [])
    has_recent_release = False
    for rel in releases_nodes:
        rel_date = parse_iso_date(rel.get("publishedAt"))
        if rel_date and (now - rel_date).days <= 180:
            has_recent_release = True
            break
    if has_recent_release:
        score += 10

    # 6. Recency score (pushed_at)
    pushed_at = parse_iso_date(repo.get("pushedAt"))
    if pushed_at:
        days_since_push = (now - pushed_at).days
        if days_since_push <= 7:
            score += 40
        elif days_since_push <= 30:
            score += 30
        elif days_since_push <= 90:
            score += 20
        elif days_since_push <= 180:
            score += 10

    # 7. Popularity score: Stars/forks, capped combined at +10
    stars = repo.get("stargazerCount", 0)
    forks = repo.get("forkCount", 0)
    pop_score = min(stars + forks, 10)
    score += pop_score

    return score


def sort_repositories(
    repos: list[dict[str, Any]],
    featured_repos: list[str],
    privacy_config: dict[str, Any] | None = None,
    now: datetime.datetime | None = None,
) -> list[tuple[dict[str, Any], int]]:
    """
    Scores and sorts repositories using tie-break sequence:
      1. Score (highest first)
      2. Featured status (featured first)
      3. Most recent pushed_at
      4. More stars
      5. Alphabetical name
    """
    scored = []
    for r in repos:
        s = calculate_repo_score(r, featured_repos, privacy_config, now)
        if s >= 0:
            scored.append((r, s))

    def sort_key(item: tuple[dict[str, Any], int]):
        r, s = item
        name = r.get("name", "")
        featured = 1 if name in featured_repos else 0
        pushed = r.get("pushedAt") or ""
        stars = r.get("stargazerCount", 0)
        # Sort descending by score, featured, pushed_at, stars, and ascending by name
        return (-s, -featured, pushed, -stars, name)

    # Python sort is stable; sorting by key with negated values
    # For pushed_at string: ISO strings sort chronologically
    scored.sort(
        key=lambda item: (
            -item[1],
            0 if item[0].get("name", "") in featured_repos else 1,
            -(parse_iso_date(item[0].get("pushedAt")).timestamp() if parse_iso_date(item[0].get("pushedAt")) else 0),
            -item[0].get("stargazerCount", 0),
            item[0].get("name", "").lower(),
        )
    )

    return scored


def fetch_graphql_data(login: str, repo_limit: int, token: str) -> dict[str, Any]:
    """Fetches user and repository data from GitHub GraphQL API."""
    url = "https://api.github.com/graphql"
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "profile-readme-intelligence",
    }
    payload = {
        "query": GRAPHQL_QUERY,
        "variables": {
            "login": login,
            "repoLimit": repo_limit,
        },
    }

    resp = requests.post(url, json=payload, headers=headers, timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(
            f"GitHub API returned HTTP {resp.status_code}: {resp.text[:200]}"
        )

    data = resp.json()
    if "errors" in data and not data.get("data"):
        raise RuntimeError(f"GitHub GraphQL error: {data['errors']}")

    return data.get("data", {})


def build_context_json(
    raw_user: dict[str, Any],
    top_repos: list[dict[str, Any]],
    facts: dict[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    """Constructs schema v1 context.json structure."""
    contrib = raw_user.get("contributionsCollection", {})

    allowed_orgs = []
    writing_config = facts.get("writing", {})
    allowed_orgs.extend(writing_config.get("allowed_organizations", []))
    if not allowed_orgs:
        allowed_orgs.extend(facts.get("allowed_organizations", []))

    processed_repos = []
    allowed_repos = []

    for r in top_repos:
        name = r.get("name", "")
        allowed_repos.append(name)

        topics = [
            t.get("topic", {}).get("name", "")
            for t in r.get("repositoryTopics", {}).get("nodes", [])
            if t.get("topic", {}).get("name")
        ]

        releases = [
            {
                "name": rel.get("name"),
                "tagName": rel.get("tagName"),
                "publishedAt": rel.get("publishedAt"),
                "url": rel.get("url"),
            }
            for rel in r.get("releases", {}).get("nodes", [])
        ]

        commits = []
        commit_nodes = (
            r.get("defaultBranchRef", {})
            .get("target", {})
            .get("history", {})
            .get("nodes", [])
        )
        for c in commit_nodes:
            commits.append({
                "date": c.get("committedDate"),
                "headline": sanitize_text(c.get("messageHeadline"), max_length=160),
                "url": c.get("url"),
            })

        processed_repos.append({
            "name": name,
            "url": r.get("url"),
            "homepageUrl": r.get("homepageUrl"),
            "description": sanitize_text(r.get("description"), max_length=400),
            "primary_language": (r.get("primaryLanguage") or {}).get("name"),
            "topics": topics,
            "is_archived": r.get("isArchived", False),
            "is_fork": r.get("isFork", False),
            "is_private": r.get("isPrivate", False),
            "featured": name in facts.get("featured_repositories", []),
            "pushed_at": r.get("pushedAt"),
            "stars": r.get("stargazerCount", 0),
            "forks": r.get("forkCount", 0),
            "releases": releases,
            "recent_commits": commits,
        })

    return {
        "schema_version": 1,
        "generated_at": generated_at,
        "profile": {
            "login": raw_user.get("login"),
            "name": raw_user.get("name") or facts.get("identity", {}).get("display_name"),
            "bio": raw_user.get("bio"),
            "location": raw_user.get("location") or facts.get("identity", {}).get("location"),
            "followers": (raw_user.get("followers") or {}).get("totalCount", 0),
        },
        "contributions": {
            "commits": contrib.get("totalCommitContributions", 0),
            "pull_requests": contrib.get("totalPullRequestContributions", 0),
            "issues": contrib.get("totalIssueContributions", 0),
            "repositories": contrib.get("totalRepositoryContributions", 0),
        },
        "repositories": processed_repos,
        "allowed_repositories": allowed_repos,
        "allowed_organizations": allowed_orgs,
    }


def build_context_md(context_data: dict[str, Any], facts: dict[str, Any]) -> str:
    """Constructs clean compact context.md model evidence."""
    identity = facts.get("identity", {})
    positioning = facts.get("positioning", [])
    domains = facts.get("approved_domains", [])
    contrib = context_data.get("contributions", {})

    lines = [
        "# Profile evidence",
        "",
        "## Approved profile facts",
        "",
        f"- Display name: {identity.get('display_name', '')}",
        f"- Location: {identity.get('location', '')}",
        f"- Positioning: {'; '.join(positioning)}",
        f"- Approved domains: {'; '.join(domains)}",
        "",
        "## GitHub activity",
        "",
    ]

    contrib_items = []
    if contrib.get("commits", 0) > 0:
        contrib_items.append(f"{contrib['commits']} commits")
    if contrib.get("pull_requests", 0) > 0:
        contrib_items.append(f"{contrib['pull_requests']} pull requests")
    if contrib.get("issues", 0) > 0:
        contrib_items.append(f"{contrib['issues']} issues")
    if contrib.get("repositories", 0) > 0:
        contrib_items.append(f"{contrib['repositories']} contributed repositories")

    if contrib_items:
        lines.append(f"- Public contribution summary: {', '.join(contrib_items)}")
    else:
        lines.append("- Public contribution summary: active contributions across public repositories")

    lines.extend([
        "",
        "## Eligible repositories",
    ])

    for repo in context_data.get("repositories", []):
        name = repo.get("name", "")
        desc = repo.get("description") or "none"
        lang = repo.get("primary_language") or "none"
        topics = ", ".join(repo.get("topics", [])) or "none"
        pushed = (repo.get("pushed_at") or "")[:10] or "unknown"

        releases = repo.get("releases", [])
        rel_str = releases[0].get("tagName") if releases else "none"

        lines.extend([
            "",
            f"### {name}",
            "",
            f"- Repository name: `{name}`",
            f"- Description: {desc}",
            f"- Primary language: {lang}",
            f"- Topics: {topics}",
            f"- Last pushed: {pushed}",
            f"- Recent releases: {rel_str}",
        ])

        commits = repo.get("recent_commits", [])
        if commits:
            lines.append("- Recent commit headlines:")
            for c in commits[:3]:
                h = c.get("headline", "").strip()
                if h:
                    lines.append(f"  - {h}")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Collect public GitHub signals and generate context artifacts."
    )
    parser.add_argument("--login", required=True, help="Target GitHub login handle")
    parser.add_argument("--facts", required=True, help="Path to profile-facts.yml")
    parser.add_argument("--json-out", required=True, help="Output path for context.json")
    parser.add_argument("--markdown-out", required=True, help="Output path for context.md")
    parser.add_argument("--repo-limit", type=int, default=20, help="Repository query limit (default: 20)")
    parser.add_argument("--fixture", help="Optional offline raw GraphQL JSON response fixture for testing")

    args = parser.parse_args()

    if not os.path.isfile(args.facts):
        print(f"Error: Profile facts file not found: {args.facts}", file=sys.stderr)
        return 2

    try:
        with open(args.facts, "r", encoding="utf-8") as f:
            facts = yaml.safe_load(f)
    except Exception as err:
        print(f"Error parsing profile-facts.yml: {err}", file=sys.stderr)
        return 3

    raw_user: dict[str, Any] = {}

    if args.fixture:
        try:
            with open(args.fixture, "r", encoding="utf-8") as f:
                fixture_data = json.load(f)
            raw_user = fixture_data.get("user") or fixture_data.get("data", {}).get("user", {})
        except Exception as err:
            print(f"Error loading fixture: {err}", file=sys.stderr)
            return 2
    else:
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not token:
            print(
                "Error: GH_TOKEN or GITHUB_TOKEN environment variable is required to fetch live GitHub data.",
                file=sys.stderr,
            )
            return 1

        try:
            data = fetch_graphql_data(args.login, args.repo_limit, token)
            raw_user = data.get("user", {})
        except Exception as err:
            print(f"Error fetching GitHub data: {err}", file=sys.stderr)
            return 1

    if not raw_user:
        print(f"Error: No user data returned for login {args.login!r}", file=sys.stderr)
        return 1

    featured_repos = facts.get("featured_repositories", [])
    privacy_config = facts.get("privacy", {})
    raw_repos = (
        raw_user.get("repositories", {}).get("nodes", [])
    )

    scored_repos = sort_repositories(raw_repos, featured_repos, privacy_config)
    # Select at most five repositories
    top_repos = [r for r, s in scored_repos[:5]]

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    context_data = build_context_json(raw_user, top_repos, facts, now_iso)
    context_md = build_context_md(context_data, facts)

    os.makedirs(os.path.dirname(os.path.abspath(args.json_out)), exist_ok=True)
    with open(args.json_out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(context_data, f, indent=2)

    os.makedirs(os.path.dirname(os.path.abspath(args.markdown_out)), exist_ok=True)
    with open(args.markdown_out, "w", encoding="utf-8", newline="\n") as f:
        f.write(context_md)

    print(f"Successfully generated {args.json_out} and {args.markdown_out}")
    print(f"Selected {len(top_repos)} eligible repositories: {[r.get('name') for r in top_repos]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
