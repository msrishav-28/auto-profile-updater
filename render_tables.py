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

TABLE_BEGIN_REGEX = re.compile(r"^\s*<!-- TABLE:BEGIN:(?P<name>[A-Z0-9_]+) -->\s*$")
TABLE_END_REGEX = re.compile(r"^\s*<!-- TABLE:END:(?P<name>[A-Z0-9_]+) -->\s*$")
BADGE_BEGIN_REGEX = re.compile(r"^\s*<!-- BADGES:BEGIN:(?P<name>[A-Z0-9_]+) -->\s*$")
BADGE_END_REGEX = re.compile(r"^\s*<!-- BADGES:END:(?P<name>[A-Z0-9_]+) -->\s*$")

# Common tech stacks mapped to their Shields.io configuration
TECH_BADGE_MAP = {
    "python": ("Python", "3776AB", "python"),
    "javascript": ("JavaScript", "F7DF1E", "javascript"),
    "typescript": ("TypeScript", "3178C6", "typescript"),
    "react": ("React", "61DAFB", "react"),
    "next.js": ("Next.js", "000000", "nextdotjs"),
    "vue": ("Vue.js", "4FC08D", "vuedotjs"),
    "html": ("HTML5", "E34F26", "html5"),
    "css": ("CSS3", "1572B6", "css3"),
    "node.js": ("Node.js", "339939", "nodedotjs"),
    "go": ("Go", "00ADD8", "go"),
    "rust": ("Rust", "000000", "rust"),
    "java": ("Java", "ED8B00", "java"),
    "c++": ("C++", "00599C", "cplusplus"),
    "c#": ("C#", "239120", "csharp"),
    "ruby": ("Ruby", "CC342D", "ruby"),
    "php": ("PHP", "777BB4", "php"),
    "docker": ("Docker", "2496ED", "docker"),
    "kubernetes": ("Kubernetes", "326CE5", "kubernetes"),
    "aws": ("AWS", "232F3E", "amazonaws"),
    "gcp": ("Google Cloud", "4285F4", "googlecloud"),
    "azure": ("Azure", "0089D6", "microsoftazure"),
    "fastapi": ("FastAPI", "009688", "fastapi"),
    "supabase": ("Supabase", "3ECF8E", "supabase"),
    "postgres": ("PostgreSQL", "4169E1", "postgresql"),
    "mysql": ("MySQL", "4479A1", "mysql"),
    "mongodb": ("MongoDB", "47A248", "mongodb"),
    "redis": ("Redis", "DC382D", "redis"),
    "linux": ("Linux", "FCC624", "linux"),
}

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

def find_regions(content: str) -> list[tuple[str, str, int, int]]:
    """Returns a list of regions: (type, name, begin_idx, end_idx)"""
    lines = content.splitlines(keepends=True)
    regions = []
    open_region = None
    open_type = None
    open_idx = -1

    for i, line in enumerate(lines):
        tb_match = TABLE_BEGIN_REGEX.match(line)
        te_match = TABLE_END_REGEX.match(line)
        bb_match = BADGE_BEGIN_REGEX.match(line)
        be_match = BADGE_END_REGEX.match(line)
        
        if tb_match or bb_match:
            name = tb_match.group("name") if tb_match else bb_match.group("name")
            rtype = "TABLE" if tb_match else "BADGES"
            open_region = name
            open_type = rtype
            open_idx = i
        elif te_match or be_match:
            name = te_match.group("name") if te_match else be_match.group("name")
            rtype = "TABLE" if te_match else "BADGES"
            if open_region == name and open_type == rtype:
                regions.append((open_type, open_region, open_idx, i))
                open_region = None
                open_type = None

    return regions

def generate_top_languages_badges(context: dict) -> list[str]:
    repos = context.get("repositories", [])
    if not repos:
        return []

    # Tally up languages and topics
    tech_counts = {}
    for repo in repos:
        lang = repo.get("primary_language")
        if lang:
            tech_counts[lang.lower()] = tech_counts.get(lang.lower(), 0) + 1
        
        for topic in repo.get("topics", []):
            tech_counts[topic.lower()] = tech_counts.get(topic.lower(), 0) + 1

    # Sort by frequency
    sorted_tech = sorted(tech_counts.items(), key=lambda x: x[1], reverse=True)
    
    # Generate badges for known tech
    badges = []
    for tech, count in sorted_tech:
        if tech in TECH_BADGE_MAP:
            label, color, logo = TECH_BADGE_MAP[tech]
            # GitHub badge format
            badge_md = f"![{label}](https://img.shields.io/badge/{label.replace(' ', '%20')}-{color}?style=flat-square&logo={logo}&logoColor=white)"
            if badge_md not in badges:
                badges.append(badge_md)
                
        if len(badges) >= 10: # Limit to top 10 technologies
            break
            
    if not badges:
        return []
        
    # Return as a single line wrapped in a div/p or just joined by spaces
    return [" ".join(badges)]

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
    regions = find_regions(readme_content)
    
    if not regions:
        print(f"No TABLE or BADGE markers found in {readme_path}. No regions updated.")
        return
        
    # Replace from bottom to top to avoid shifting indices
    for rtype, name, b, e in reversed(regions):
        if rtype == "TABLE" and name == "ACTIVE_BUILDS":
            rows = generate_active_builds_rows(context, facts)
            new_lines = [row + "\n" for row in rows]
            lines[b+1 : e] = new_lines
            print(f"Updated table region: {name}")
        elif rtype == "BADGES" and name == "TOP_LANGUAGES":
            rows = generate_top_languages_badges(context)
            new_lines = [row + "\n" for row in rows]
            lines[b+1 : e] = new_lines
            print(f"Updated badge region: {name}")
        else:
            print(f"Warning: Unknown region type/name '{rtype}:{name}'. Skipping.")

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
