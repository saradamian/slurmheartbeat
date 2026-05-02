#!/bin/bash
# Run tests and linter for Slurm Heartbeat daemon
# Usage: ./run_tests.sh [options]

set -e

# Default options
OPTIONS="${OPTIONS:-}"
COVERAGE="${COVERAGE:-false}"
LINT="${LINT:-true}"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --coverage)
            COVERAGE=true
            shift
            ;;
        --no-lint)
            LINT=false
            shift
            ;;
        -v|--verbose)
            OPTIONS="$OPTIONS -v"
            shift
            ;;
        -q|--quiet)
            OPTIONS="$OPTIONS -q"
            shift
            ;;
        *)
            OPTIONS="$OPTIONS $1"
            shift
            ;;
    esac
done

echo "Running Slurm Heartbeat checks..."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run linter if enabled
if [ "$LINT" = true ]; then
    echo "Running Ruff linter..."
    ruff check .
    
    echo "Running Ruff formatter check..."
    ruff format . --check
    
    echo "Lint checks passed!"
fi

# Run tests
echo "Running tests..."
if [ "$COVERAGE" = true ]; then
    echo "Running tests with coverage..."
    pytest tests/ $OPTIONS --cov=slurmheartbeat --cov-report=html --cov-report=term-missing
else
    pytest tests/ $OPTIONS
fi

echo "All checks completed!"
