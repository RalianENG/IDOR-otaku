# Contributing to IDOR-otaku

Thank you for your interest in contributing to IDOR-otaku!

## Getting Started

```bash
git clone https://github.com/RalianENG/IDOR-otaku.git
cd IDOR-otaku
python -m venv .venv
.venv\Scripts\activate   # Windows
source .venv/bin/activate # macOS/Linux
pip install -e ".[dev]"
```

## Branch Naming

| Prefix | Use Case | Example |
|--------|----------|---------|
| `feature/` | New features | `feature/add-csv-export` |
| `fix/` | Bug fixes | `fix/parsing-error` |
| `chore/` | Maintenance, CI, docs | `chore/update-deps` |
| `refactor/` | Code refactoring | `refactor/cleanup-api` |

## Commit Messages

Use clear, descriptive commit messages:

```
<type>: <short summary>
```

Types: `feat`, `fix`, `chore`, `refactor`, `docs`, `test`, `ci`

Examples:
- `feat: add SARIF export command`
- `fix: handle empty response in tracker`
- `chore: bump mitmproxy to 11.0`

## Development Workflow

1. Create a branch from `main` (e.g., `feature/add-new-command`)
2. Make your changes
3. Run tests and lint before submitting

```bash
# Lint
ruff check src/

# Test
pytest

# Test with coverage
pytest --cov=idotaku --cov-report=term-missing
```

## Pull Requests

- Keep PRs focused on a single change
- Add tests for new functionality
- Ensure all tests pass and lint is clean
- Write a clear description of what your PR does and why

## Bug Reports

Open an issue on [GitHub Issues](https://github.com/RalianENG/IDOR-otaku/issues) with:

- Steps to reproduce
- Expected behavior
- Actual behavior
- Python version and OS

## Code Style

- Follow existing code patterns
- Line length: 100 characters (configured in `pyproject.toml`)
- Linter: ruff

## Security Vulnerabilities

Do **not** open a public issue for security vulnerabilities. See [SECURITY.md](SECURITY.md) for reporting instructions.