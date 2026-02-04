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

## Development Workflow

1. Create a branch from `main`
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