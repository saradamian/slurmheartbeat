# Linting and Formatting with Ruff

This document describes the linting and formatting setup for the Slurm Heartbeat project.

## Overview

We use **Ruff** as our primary linter and formatter, replacing traditional tools like flake8, isort, and black.

### Why Ruff?

- **Speed**: 10-100x faster than traditional Python linters
- **Comprehensive**: Over 900 rules covering multiple tools
- **Single tool**: Replaces flake8, isort, black, pyupgrade, and more
- **IDE integration**: Works with all major editors
- **Auto-fix**: Automatically fixes many common issues

## Installation

Ruff is included in the development dependencies:

```bash
pip install -e ".[dev]"
```

## Configuration

Ruff is configured in `pyproject.toml` under `[tool.ruff]`. Key settings:

- **Target version**: Python 3.10+
- **Line length**: 100 characters
- **Quote style**: Double quotes
- **Indent style**: 4 spaces

## Running Ruff

### Linting

Check for issues:

```bash
ruff check .
```

Auto-fix issues:

```bash
ruff check . --fix
```

Check specific file:

```bash
ruff check path/to/file.py
```

### Formatting

Format code:

```bash
ruff format .
```

Check formatting without changes:

```bash
ruff format . --check
```

## Rules

### Enabled Rules

| Category | Rules | Description |
|----------|-------|-------------|
| **E** | pycodestyle | Code style errors |
| **W** | pycodestyle | Code style warnings |
| **F** | Pyflakes | Syntax and logic errors |
| **I** | isort | Import sorting |
| **B** | flake8-bugbear | Common bugs |
| **C4** | flake8-comprehensions | Comprehension improvements |
| **UP** | pyupgrade | Modern Python syntax |
| **TC** | flake8-type-checking | Type checking imports |
| **S** | flake8-bandit | Security issues |
| **RUF** | Ruff-specific | Ruff-specific rules |
| **ASYNC** | flake8-async | Async/await issues |
| **SIM** | flake8-simplify | Code simplification |

### Ignored Rules

- `E501`: Line too long (handled by formatter)
- `B008`: Function calls in argument defaults (needed for dataclasses)
- `S101`: Assertions in tests (allowed)
- `S104`: 0.0.0.0 binding (allowed for server)

### Per-File Rules

**Tests** (`tests/*`):
- Allow assertions (`S101`)
- Allow hardcoded passwords in tests (`S105`, `S106`)

**Server code** (`slurmheartbeat/server/*.py`):
- Allow 0.0.0.0 binding (`S104`)

## Pre-commit Hooks

For automatic linting before commits, install pre-commit hooks:

```bash
pip install pre-commit
pre-commit install
```

This will run Ruff automatically on every commit.

## Editor Integration

### VS Code

Add to `.vscode/settings.json`:

```json
{
    "python.linting.enabled": true,
    "python.linting.ruffEnabled": true,
    "python.formatting.provider": "ruff",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
        "source.fixAll.ruff": "explicit"
    }
}
```

### PyCharm

1. Install Ruff plugin
2. Configure in Settings → Tools → Ruff
3. Enable "Run on save"

### Vim/Neovim

Use [coc-ruff](https://github.com/ye71/coc-ruff) or [nvim-lspconfig](https://github.com/neovim/nvim-lspconfig).

## Common Issues

### Import Sorting

Ruff automatically sorts imports. To fix:

```bash
ruff check . --fix
```

### Type Checking

For type hints, use `from __future__ import annotations` at the top of files.

### Async Code

For async functions, ensure you're using `asyncio.run()` or proper event loop management.

## Migration from Other Tools

If migrating from flake8, black, or isort:

1. Remove old configuration files (`.flake8`, `setup.cfg`, `tox.ini` sections)
2. Run `ruff check . --fix` to auto-fix issues
3. Run `ruff format .` to format code
4. Update CI/CD pipelines to use Ruff

## Troubleshooting

### "Rule X is not recognized"

Update Ruff to the latest version:

```bash
pip install -U ruff
```

### "File too long"

Increase line-length in `pyproject.toml` or break up long lines.

### "Import sorting failed"

Run `ruff check . --fix` to auto-fix import sorting.

## Best Practices

1. **Run before commit**: Use pre-commit hooks
2. **Fix automatically**: Use `--fix` flag when possible
3. **Review changes**: Always review auto-fixes
4. **Keep updated**: Regularly update Ruff version
5. **Document exceptions**: Use inline comments for intentional ignores

## CI/CD Integration

Add to your CI pipeline:

```yaml
lint:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4
      with:
        python-version: "3.10"
    - name: Install dependencies
      run: pip install -e ".[dev]"
    - name: Run Ruff
      run: ruff check .
    - name: Check formatting
      run: ruff format . --check
```

## Resources

- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Ruff Rules](https://docs.astral.sh/ruff/rules/)
- [Ruff Pre-commit](https://github.com/astral-sh/ruff-pre-commit)
