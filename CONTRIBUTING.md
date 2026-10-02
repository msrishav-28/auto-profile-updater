# Contributing to Auto Profile Updater

Thank you for your interest in contributing to **Auto Profile Updater**!

This project is built under strict production-engineering standards: every change must be evidence-grounded, fail-closed, and non-destructive.

---

## Operating Principles

1. **Deterministic Core:** Deterministic Python code decides whether content is safe; the language model is never trusted to self-regulate.
2. **Fail-Closed:** If markers are missing, schemas are invalid, or API responses fail, the pipeline halts without corrupting files.
3. **No Dead or Incomplete Code:** No unused functions, stubs, TODOs, or placeholder implementations.
4. **Exhaustive Testing:** Every new policy rule, edge case, or parser feature must be accompanied by unit tests.

---

## Development Setup

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/msrishav-28/auto-profile-updater.git
   cd auto-profile-updater
   ```

2. Create and activate a Python virtual environment (Python 3.11+ required):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```

4. Run the test suite to verify your baseline:
   ```bash
   python -m pytest -v
   ```

---

## Testing Guidelines

* Tests live in the `tests/` directory.
* Run tests with `pytest -v`.
* Offline testing is mandatory: do not require live GitHub credentials or network connectivity in the standard test suite. Use fixtures in `tests/fixtures/`.
* All 56 existing tests must pass before submitting a pull request.

---

## Pull Request Process

1. Create a descriptive feature branch:
   ```bash
   git checkout -b feat/your-feature-name
   ```
2. Commit your changes with clear, semantic commit messages (e.g., `feat: ...`, `fix: ...`, `docs: ...`).
3. Ensure all tests pass and formatting is clean.
4. Open a pull request against the `main` branch.
5. In your PR description, explain:
   - What problem was solved.
   - Any edge cases considered.
   - How the change was tested.

---

## Code of Conduct

Be welcoming, professional, and respectful to all contributors and community members.
