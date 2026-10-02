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

# Common tech stacks mapped to their Shields.io configuration and Category
TECH_BADGE_MAP = {
    "python": ("Python", "000000", "python", "Core"),
    "javascript": ("JavaScript", "000000", "javascript", "Core"),
    "typescript": ("TypeScript", "000000", "typescript", "Core"),
    "sql": ("SQL", "000000", "postgresql", "Core"),
    "java": ("Java", "000000", "java", "Core"),
    "c++": ("C++", "000000", "cplusplus", "Core"),
    
    "pytorch": ("PyTorch", "000000", "pytorch", "AI / ML"),
    "tensorflow": ("TensorFlow", "000000", "tensorflow", "AI / ML"),
    "scikit-learn": ("scikit-learn", "000000", "scikitlearn", "AI / ML"),
    "opencv": ("OpenCV", "000000", "opencv", "AI / ML"),
    "huggingface": ("Hugging Face", "000000", "huggingface", "AI / ML"),
    "pandas": ("pandas", "000000", "pandas", "AI / ML"),
    "numpy": ("NumPy", "000000", "numpy", "AI / ML"),
    
    "react": ("React", "000000", "react", "Full-stack"),
    "next.js": ("Next.js", "000000", "nextdotjs", "Full-stack"),
    "react native": ("React Native", "000000", "react", "Full-stack"),
    "vue": ("Vue.js", "000000", "vuedotjs", "Full-stack"),
    "fastapi": ("FastAPI", "000000", "fastapi", "Full-stack"),
    "flask": ("Flask", "000000", "flask", "Full-stack"),
    "node.js": ("Node.js", "000000", "nodedotjs", "Full-stack"),
    "html": ("HTML5", "000000", "html5", "Full-stack"),
    "css": ("CSS3", "000000", "css3", "Full-stack"),
    
    "postgres": ("PostgreSQL", "000000", "postgresql", "Data / systems"),
    "postgresql": ("PostgreSQL", "000000", "postgresql", "Data / systems"),
    "supabase": ("Supabase", "000000", "supabase", "Data / systems"),
    "mongodb": ("MongoDB", "000000", "mongodb", "Data / systems"),
    "firebase": ("Firebase", "000000", "firebase", "Data / systems"),
    "docker": ("Docker", "000000", "docker", "Data / systems"),
    "kubernetes": ("Kubernetes", "000000", "kubernetes", "Data / systems"),
    "github actions": ("GitHub Actions", "000000", "githubactions", "Data / systems"),
    "aws": ("AWS", "000000", "amazonaws", "Data / systems"),
    "gcp": ("Google Cloud", "000000", "googlecloud", "Data / systems"),
    
    "langchain": ("LangChain", "000000", "langchain", "Exploring / research"),
    "langgraph": ("LangGraph", "000000", "langchain", "Exploring / research"),
    "rag": ("RAG", "000000", "openai", "Exploring / research"),
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

    tech_counts = {}
    for repo in repos:
        lang = repo.get("primary_language")
        if lang:
            tech_counts[lang.lower()] = tech_counts.get(lang.lower(), 0) + 1
        for topic in repo.get("topics", []):
            tech_counts[topic.lower()] = tech_counts.get(topic.lower(), 0) + 1

    sorted_tech = sorted(tech_counts.items(), key=lambda x: x[1], reverse=True)
    
    badges = []
    for tech, count in sorted_tech:
        if tech in TECH_BADGE_MAP:
            label, color, logo, _ = TECH_BADGE_MAP[tech]
            badge_md = f"![{label}](https://img.shields.io/badge/{label.replace(' ', '%20')}-{color}?style=flat-square&logo={logo}&logoColor=white)"
            if badge_md not in badges:
                badges.append(badge_md)
        if len(badges) >= 10:
            break
            
    if not badges:
        return []
    return [" ".join(badges)]

def generate_stack_trace_html(context: dict) -> list[str]:
    repos = context.get("repositories", [])
    if not repos:
        return []

    # Get unique tech from repos
    tech_set = set()
    for repo in repos:
        lang = repo.get("primary_language")
        if lang:
            tech_set.add(lang.lower())
        for topic in repo.get("topics", []):
            tech_set.add(topic.lower())
            
    # Group by category
    categories = {
        "Core": [],
        "AI / ML": [],
        "Full-stack": [],
        "Data / systems": [],
        "Exploring / research": []
    }
    
    for tech in tech_set:
        if tech in TECH_BADGE_MAP:
            label, color, logo, cat = TECH_BADGE_MAP[tech]
            badge_md = f'<img src="https://img.shields.io/badge/{label.replace(" ", "%20")}-{color}?style=for-the-badge&logo={logo}&logoColor=00FF41" alt="{label}" />'
            if cat in categories and badge_md not in categories[cat]:
                categories[cat].append(badge_md)
                
    # Build HTML table rows
    html_lines = []
    html_lines.append("<table>")
    html_lines.append("  <tr>")
    html_lines.append('    <th align="left">Layer</th>')
    html_lines.append('    <th align="left">Worked with</th>')
    html_lines.append("  </tr>")
    
    for cat, badges in categories.items():
        if not badges:
            continue
        html_lines.append("  <tr>")
        html_lines.append(f"    <td><strong>{cat}</strong></td>")
        html_lines.append("    <td>")
        for b in badges:
            html_lines.append(f"      {b}")
        html_lines.append("    </td>")
        html_lines.append("  </tr>")
        
    html_lines.append("</table>")
    return html_lines

def generate_current_focus_rows(facts: dict) -> list[str]:
    focus_list = facts.get("manual_current_focus", [])
    if not focus_list:
        return ["| No current focus specified | |"]
        
    rows = []
    for item in focus_list:
        rows.append(f"| {item} | Active |")
    return rows

def generate_github_stats(context: dict) -> list[str]:
    # Placeholder for a generic GitHub stats table based on context.json
    repos = context.get("repositories", [])
    total_stars = sum(repo.get("stars", 0) for repo in repos)
    total_repos = len(repos)
    
    rows = []
    rows.append(f"| Total Public Repositories | {total_repos} |")
    rows.append(f"| Total Stars Earned | {total_stars} |")
    if repos:
        most_starred = max(repos, key=lambda x: x.get("stargazers", 0))
        rows.append(f"| Most Starred Repository | [{most_starred.get('name')}]({most_starred.get('url')}) ({most_starred.get('stargazers')} ⭐) |")
        
    return rows

def generate_latest_posts(facts: dict) -> list[str]:
    # In a full implementation, this would fetch from an RSS feed URL provided in facts
    # For now, we return a placeholder table row
    blog_url = facts.get("blog_rss_url")
    if not blog_url:
        return ["| No RSS feed configured. Add `blog_rss_url` to profile-facts.yml | |"]
    return ["| Blog support enabled | [Visit Blog](" + blog_url + ") |"]

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
        elif rtype == "TABLE" and name == "CURRENT_FOCUS":
            rows = generate_current_focus_rows(facts)
            new_lines = [row + "\n" for row in rows]
            lines[b+1 : e] = new_lines
            print(f"Updated table region: {name}")
        elif rtype == "TABLE" and name == "STACK_TRACE":
            rows = generate_stack_trace_html(context)
            new_lines = [row + "\n" for row in rows]
            lines[b+1 : e] = new_lines
            print(f"Updated HTML table region: {name}")
        elif rtype == "TABLE" and name == "GITHUB_STATS":
            rows = generate_github_stats(context)
            new_lines = [row + "\n" for row in rows]
            lines[b+1 : e] = new_lines
            print(f"Updated table region: {name}")
        elif rtype == "TABLE" and name == "LATEST_POSTS":
            rows = generate_latest_posts(facts)
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
