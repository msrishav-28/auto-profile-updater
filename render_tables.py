#!/usr/bin/env python3
"""
render_tables.py - Deterministically updates markdown tables using GitHub context data.

This completely bypasses AI hallucination risks. It reads the raw GraphQL context data
(.artifacts/context.json) and injects perfect markdown table rows into specific marker
regions in the README (e.g. <!-- TABLE:BEGIN:ACTIVE_BUILDS -->).
"""

import argparse
import json
import os
import re
import sys
import yaml

BEGIN_REGEX = re.compile(r"^\s*<!-- TABLE:BEGIN:(?P<name>[A-Z0-9_]+) -->\s*$")
END_REGEX = re.compile(r"^\s*<!-- TABLE:END:(?P<name>[A-Z0-9_]+) -->\s*$")

def load_json(filepath: str) -> dict:
    if not os.path.exists(filepath):
        print(f"Error: Could not find {filepath}", file=sys.stderr)
        sys.exit(1)
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def load_yaml(filepath: str) -> dict:
    if not os.path.exists(filepath):
        print(f"Error: Could not find {filepath}", file=sys.stderr)
        sys.exit(1)
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def find_table_regions(content: str) -> list[tuple[str, int, int]]:
    lines = content.splitlines(keepends=True)
    regions = []
    open_region = None
    open_idx = -1

    for i, line in enumerate(lines):
        begin_match = BEGIN_REGEX.match(line)
        end_match = END_REGEX.match(line)
        
        if begin_match:
            name = begin_match.group("name")
            open_region = name
            open_idx = i
        elif end_match:
            name = end_match.group("name")
            if open_region == name:
                regions.append((open_region, open_idx, i))
                open_region = None

    return regions

def generate_active_builds_rows(context: dict, facts: dict) -> list[str]:
    # We prioritize featured repositories, or fallback to the top repositories from context
    featured = facts.get("featured_repositories", [])
    repos = context.get("repositories", [])
    
    if not repos:
        return ["| No public repositories found | | | | |"]

    # Filter and sort repos based on featured list, then by score
    repo_map = {r["name"].lower(): r for r in repos}
    
    selected_repos = []
    for f_repo in featured:
        if f_repo.lower() in repo_map:
            selected_repos.append(repo_map[f_repo.lower()])
            
    # If no featured repos or they weren't found, just take the top 5
    if not selected_repos:
        selected_repos = sorted(repos, key=lambda x: x.get("score", 0), reverse=True)[:5]

    rows = []
    for repo in selected_repos:
        name = repo.get("name", "")
        desc = repo.get("description") or "No description available."
        
        # Build stack string
        stack_parts = []
        if repo.get("primary_language"):
            stack_parts.append(repo["primary_language"])
        topics = repo.get("topics", [])
        if topics:
            stack_parts.extend(topics[:3]) # Limit to top 3 topics
            
        stack = ", ".join(stack_parts) if stack_parts else "N/A"
        
        # Link construction
        url = repo.get("url", "")
        homepage = repo.get("homepageUrl", "")
        
        links = f"[Repo]({url})"
        if homepage:
            links += f" / [Live]({homepage})"
            status = "Live"
        else:
            status = "Development"
            
        # Format the row
        # | Project | What it does | Stack | Status | Link |
        # Strip newlines from description just in case
        desc = desc.replace("\n", " ").replace("|", "-")
        rows.append(f"| {name} | {desc} | {stack} | {status} | {links} |")
        
    return rows

def process_readme(readme_path: str, context_path: str, facts_path: str):
    context = load_json(context_path)
    facts = load_yaml(facts_path)
    
    with open(readme_path, "r", encoding="utf-8") as f:
        readme_content = f.read()
        
    lines = readme_content.splitlines(keepends=True)
    regions = find_table_regions(readme_content)
    
    if not regions:
        print(f"No TABLE markers found in {readme_path}. No tables updated.")
        return
        
    # Replace from bottom to top to avoid shifting indices
    for name, b, e in reversed(regions):
        if name == "ACTIVE_BUILDS":
            rows = generate_active_builds_rows(context, facts)
            # Add newlines
            new_lines = [row + "\n" for row in rows]
            lines[b+1 : e] = new_lines
            print(f"Updated table region: {name}")
        else:
            print(f"Warning: Unknown table region '{name}'. Skipping.")

    with open(readme_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(lines))
    print("README update complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deterministically render markdown tables.")
    parser.add_argument("--readme", required=True, help="Path to README.md")
    parser.add_argument("--context", required=True, help="Path to context.json")
    parser.add_argument("--facts", required=True, help="Path to profile-facts.yml")
    args = parser.parse_args()
    
    process_readme(args.readme, args.context, args.facts)
