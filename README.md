# Auto Profile Updater ⚡

> **GitHub Profile Intelligence System**: An evidence-grounded, zero-hallucination automation engine that periodically updates your public GitHub profile biography with real, verifiable shipping activity — without ever touching your custom layouts, tables, or GIFs.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-brightgreen.svg)](pyproject.toml)
[![Tests: 34 Passing](https://img.shields.io/badge/Tests-34%20Passing-brightgreen.svg)](tests/)
[![Powered by: GitHub Models](https://img.shields.io/badge/Powered%20By-GitHub%20Models-blueviolet.svg)](.github/prompts/profile.prompt.yml)
[![Zero External API Keys](https://img.shields.io/badge/API%20Keys-Zero%20External-success.svg)](#security-and-trust-boundaries)

---

## Why Auto Profile Updater?

Profile READMEs get stale fast. Manual rewrites are tedious, but generic auto-generators produce AI hype, hallucinate claims, spam emojis, and trash carefully designed layouts.

**Auto Profile Updater** operates as a **strictly constrained editorial pipeline**:
1. **Verifiable Signals Only:** Inspects your real, public repository activity, commits, and releases via the GitHub GraphQL API.
2. **Untrusted Evidence Sanitization:** Redacts prompt-injection attempts, strips external URLs, and scrubs secret patterns before feeding context to the model.
3. **Constrained Writing Model:** Powered by GitHub Models (`openai/gpt-4o-mini`) through native GitHub Actions inference — no external API accounts or credit cards required.
4. **Independent Deterministic Validator:** An independent gatekeeper inspects the generated output and fails closed if it detects prohibited buzzwords (`10x`, `ninja`, `guru`), unapproved organizations, unlisted repositories, or malformed sections.
5. **Human Approval by Default:** Submits updates as reviewable pull requests. Nothing touches your public profile without your consent.

---

## How It Handles Complicated READMEs (Tables, GIFs, & Workflows)

> **Will this work if my profile README has custom HTML, tables, GIFs, badges, and other workflows?**  
> **Yes. 100%.**

The system enforces a **Strict Marker Isolation Boundary**. It only reads and splices content strictly between two designated HTML comment tags:

```markdown
<!-- AI:BEGIN -->
... only this dynamic region is generated and refreshed ...
<!-- AI:END -->
```

### The Invariant Guarantee
* **Zero Layout Corruption:** Everything above `<!-- AI:BEGIN -->` and everything below `<!-- AI:END -->` is **completely immutable**.
* **Your Custom Artifacts are Safe:**
  * Terminal headers & animated SVGs `<img src="..." />` remain untouched.
  * Custom shields.io badges remain untouched.
  * Multi-column Markdown project tables remain untouched.
  * Embedded GIFs, videos, and custom styling remain untouched.
  * Other background actions and CI workflows continue running unaffected.
* **Fail-Closed Protection:** If the markers are missing, duplicated, out of order, or corrupted, the tool **aborts immediately** with an error. It will never guess or overwrite your page.

### Real-World Example
```markdown
<p align="center">
  <img src="./assets/terminal-header.svg" width="100%" />
</p>

# M S Rishav Subhin
**AI/ML Engineer | Full-Stack Builder**

<!-- AI:BEGIN -->
## About Me
I build practical AI-enabled products and full-stack applications with a focus on intelligent automation...

## Current Focus
- Building agentic and automation-oriented developer tools
- Developing AI-enabled product concepts for practical user workflows

## Recently Shipped
- forgebot: automated repository operations through intelligent developer tooling
<!-- AI:END -->

## > active.builds
| Project | Stack | Status | Link |
|---|---|---|---|
| ExamSensei | FastAPI, Supabase | Live | [Demo](https://...) |

<p align="center">
  <img src="https://media.giphy.com/media/your-cool-gif.gif" />
</p>
```

---

## System Architecture

```text
 ┌────────────────────────────────────────────────────────┐
 │ GitHub Actions (Scheduled every 12h / Manual Dispatch) │
 └───────────────────────────┬────────────────────────────┘
                             │
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ Unit Test Suite (pytest - fail-fast before inference)  │
 └───────────────────────────┬────────────────────────────┘
                             │
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ collect_context.py (GraphQL activity, scoring & sanitization)
 └─────────────┬────────────────────────────┬─────────────┘
               ▼                            ▼
  .artifacts/context.json        .artifacts/context.md
  (structured validation data)   (sanitized prompt evidence)
                                            │
                                            ▼
 ┌────────────────────────────────────────────────────────┐
 │ actions/ai-inference (GitHub Models: openai/gpt-4o-mini)│
 └───────────────────────────┬────────────────────────────┘
                             │
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ validate_generation.py (Structural, Policy & Evidence) │
 └───────────────────────────┬────────────────────────────┘
                             │
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ write_readme.py (Replaces bounded marker region only)  │
 └───────────────────────────┬────────────────────────────┘
                             │
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ Pull Request Created / Updated for Human Review        │
 └────────────────────────────────────────────────────────┘
```

---

## Quick Start (Deploy for Your Profile)

### 1. Fork or Clone
Fork or use this repository as a template for your own profile automation.

### 2. Configure Your Ground Truth
Edit [`profile-facts.yml`](profile-facts.yml) with your personal data:
```yaml
schema_version: 1

identity:
  display_name: Your Name
  github_login: your-username
  location: Your City, Country
  education: Your Degree | Expected Graduation

positioning:
  - Full-Stack Developer
  - AI/ML Engineer

featured_repositories:
  - your-top-project
  - your-second-project

approved_domains:
  - web development
  - machine learning
```

### 3. Add the Safety Markers to Your Profile README
Place the marker comments in your profile repository's `README.md` where you want your dynamic summary:
```markdown
<!-- AI:BEGIN -->
<!-- AI:END -->
```

### 4. Enable GitHub Actions Permissions
In your repository settings:
1. Navigate to **Settings > Actions > General**.
2. Under **Workflow permissions**, select **Read and write permissions**.
3. Check the box **Allow GitHub Actions to create and approve pull requests**.
4. Save.

That's it! The workflow runs automatically every 12 hours or whenever you trigger it manually via the Actions tab.

---

## Security and Trust Boundaries

| Component | Trust Level | Operational Rules |
|---|---|---|
| `profile-facts.yml` | **Trusted** | Curated manually by the repository owner. Contains allowed organizations, degrees, and writing boundaries. |
| GitHub API Signals | **Untrusted** | Sanitized strictly: descriptions truncated to 400 chars, commit headlines to 160 chars, URLs stripped, and prompt injections redacted. |
| AI Generation Output | **Untrusted** | Never published directly. Must pass independent deterministic structural, policy, and evidence validation. |
| Profile README | **Immutable** | Everything outside `<!-- AI:BEGIN -->` and `<!-- AI:END -->` is strictly preserved byte-for-byte. |
| Secrets & Tokens | **Zero-Leakage** | Secrets are never passed to the model, printed in workflow logs, or saved in artifacts. |

---

## Local Development & Testing

### Prerequisites
* Python 3.11+

### Setup
```bash
# Clone the repository
git clone https://github.com/msrishav-28/auto-profile-updater.git
cd auto-profile-updater

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt
```

### Running the Test Suite
The project includes 34 exhaustive unit tests covering marker invariants, validator edge cases, prompt injection defense, and GraphQL sanitization:
```bash
python -m pytest -v
```

### Running Local CLI Tools
```bash
# 1. Collect context from an offline fixture (or live with GH_TOKEN)
python collect_context.py \
  --login msrishav-28 \
  --facts profile-facts.yml \
  --json-out .artifacts/context.json \
  --markdown-out .artifacts/context.md \
  --fixture tests/fixtures/raw_graphql_response.json

# 2. Extract existing dynamic region
python write_readme.py \
  --extract \
  --readme example-profile-readme.md \
  --output .artifacts/existing-dynamic-region.md

# 3. Validate a candidate
python validate_generation.py \
  --generated tests/fixtures/generated-valid.md \
  --context .artifacts/context.json \
  --facts profile-facts.yml \
  --report .artifacts/validation-report.json

# 4. Replace marker-bounded region
python write_readme.py \
  --readme example-profile-readme.md \
  --generated tests/fixtures/generated-valid.md
```

---

## Repository Layout

```text
auto-profile-updater/
├── README.md                                  # Open-source documentation
├── example-profile-readme.md                  # Example profile README with markers
├── profile-facts.yml                          # Human-curated ground truth facts
├── pyproject.toml                             # Packaging & tool configurations
├── requirements-dev.txt                       # Minimal pinned dependencies
├── collect_context.py                         # Signal collection & sanitization
├── validate_generation.py                     # Deterministic verification gatekeeper
├── write_readme.py                            # Safe marker-bounded README splicer
├── LICENSE                                    # MIT License
├── .gitignore                                 # Production ignore list
├── tests/
│   ├── fixtures/                              # Offline fixtures & templates
│   ├── test_collect_context.py                # Context & scoring tests
│   ├── test_validate_generation.py            # Validator & rule enforcement tests
│   └── test_write_readme.py                   # Marker invariance & safety tests
└── .github/
    ├── prompts/
    │   └── profile.prompt.yml                 # Constrained model prompt contract
    ├── workflows/
    │   ├── profile-writer.yml                 # Primary refresh & PR workflow
    │   └── notify-profile-refresh.yml         # Cross-repository dispatch helper
    └── dependabot.yml                         # Automated dependency monitoring
```

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for code quality standards, test expectations, and pull request guidelines.

---

## License

This project is licensed under the [MIT License](LICENSE).
