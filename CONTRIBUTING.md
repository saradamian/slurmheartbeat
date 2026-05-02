# Contributing to Slurm Heartbeat

Thank you for your interest in contributing to Slurm Heartbeat! This document provides guidelines for contributing to this project.

## Code of Conduct

Please be respectful and inclusive in all interactions. This project follows the [Contributor Covenant](https://www.contributor-covenant.org/) code of conduct.

## How to Contribute

### Reporting Bugs

Before creating bug reports, please check existing issues. When creating a bug report, include:

- **Clear title and description**
- **Steps to reproduce** the behavior
- **Expected vs actual behavior**
- **Environment details** (OS, Python version, Slurm version)
- **Logs or error messages** if applicable

### Suggesting Features

Feature requests are welcome. Please include:

- **Use case**: Why is this feature needed?
- **Proposed solution**: How should it work?
- **Alternatives considered**: Any other approaches?
- **Additional context**: Screenshots, diagrams, etc.

### Pull Requests

1. **Fork** the repository
2. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```
3. **Make your changes** following the coding guidelines
4. **Add tests** for new functionality
5. **Update documentation** as needed
6. **Run linter and tests**:
   ```bash
   # Run Ruff linter
   ruff check .
   
   # Run Ruff formatter
   ruff format .
   
   # Run tests
   pytest tests/ -v
   ```
7. **Ensure all checks pass** before committing
8. **Submit pull request** with clear description

## Code Style

This project uses **Ruff** for linting and formatting:

- **Line length**: 100 characters
- **Python version**: 3.10+
- **Quote style**: Double quotes
- **Indent style**: 4 spaces

### Running Linter

```bash
# Check for issues
ruff check .

# Auto-fix issues
ruff check . --fix

# Check specific file
ruff check path/to/file.py
```

### Running Formatter

```bash
# Format code
ruff format .

# Check formatting without changes
ruff format . --check
```

### Pre-commit Hooks (Optional)

To automatically run Ruff before commits, add a `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```e all pass:
   ```bash
   ./scripts/run_tests.sh
   ```
7. **Commit** with a clear message:
   ```bash
   git commit -m "feat: add your feature description"
   ```
8. **Push** to your fork and submit a pull request

## Coding Guidelines

### Python Style

- Follow [PEP 8](https://pep8.org/) conventions
- Use type hints for all function signatures
- Include docstrings for all public functions and classes
- Maximum line length: 100 characters
- Use `from __future__ import annotations` at the top of files

### Type Hints

```python
from __future__ import annotations

def process_heartbeat(
    message: dict[str, str],
    timeout: int | None = None
) -> bool:
    """Process a heartbeat message.
    
    Args:
        message: The heartbeat message to process.
        timeout: Optional timeout in seconds.
    
    Returns:
        True if processing succeeded, False otherwise.
    """
    pass
```

### Code Organization

- Keep functions focused and single-purpose
- Use data classes for structured data
- Separate concerns (client, server, protocol, etc.)
- Avoid global state

### Testing

- Write unit tests for all new functionality
- Aim for high test coverage
- Use pytest fixtures for common test setup
- Mock external dependencies (Slurm API, network)

### Documentation

- Update `README.md` for user-facing changes
- Add docstrings for new functions/classes
- Update configuration examples if needed
- Include examples where helpful

## Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-org/slurmheartbeat.git
   cd slurmheartbeat
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Generate test certificates**:
   ```bash
   ./scripts/generate_certs.sh
   ```

5. **Run tests**:
   ```bash
   ./scripts/run_tests.sh
   ```

## Review Process

1. **Automated checks**: CI runs tests, linting, and type checking
2. **Code review**: At least one maintainer review required
3. **Discussion**: Address feedback and make revisions
4. **Merge**: Maintainers will merge approved PRs

## Questions?

If you have questions, please:
- Check existing documentation
- Search existing issues
- Open a new issue for discussion

Thank you for contributing!
