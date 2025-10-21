.PHONY: clean clean-pyc clean-build clean-test clean-all test test-cov coverage coverage-html run build publish help install dev-install

# Colors for output
BLUE := \033[1;34m
GREEN := \033[1;32m
YELLOW := \033[1;33m
NC := \033[0m  # No Color

# Default target
help:
	@echo "Available targets:"
	@echo "  clean         - Remove Python bytecode and basic artifacts"
	@echo "  clean-all     - Deep clean everything (pyc, build, test, cache)"
	@echo "  clean-pyc     - Remove Python bytecode files"
	@echo "  clean-build   - Remove build artifacts"
	@echo "  clean-test    - Remove test artifacts"
	@echo "  install       - Install package in current environment"
	@echo "  dev-install   - Install package in development mode"
	@echo "  test          - Run tests"
	@echo "  coverage      - Generate test coverage report"
	@echo "  coverage-html - Open coverage HTML report"
	@echo "  run           - Run the server"
	@echo "  build         - Build the project"
	@echo "  publish       - Build and publish to PyPI"
	@echo "  lint          - Check code quality"
	@echo "  format        - Fix code formatting"
	@echo "  typecheck     - Run type checking"
	@echo "  check         - Run all checks (lint, typecheck, test)"

# Basic clean - Python bytecode and common artifacts
clean: clean-pyc clean-build
	@echo "Basic clean complete."

# Remove Python bytecode files and __pycache__ directories
clean-pyc:
	@echo "Cleaning Python bytecode files..."
	@find . -type f -name '*.pyc' -delete 2>/dev/null || true
	@find . -type f -name '*.pyo' -delete 2>/dev/null || true
	@find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true

# Remove build artifacts
clean-build:
	@echo "Cleaning build artifacts..."
	@rm -rf build/ dist/ *.egg-info 2>/dev/null || true
	@rm -rf .eggs/ 2>/dev/null || true
	@find . -name '*.egg' -exec rm -f {} + 2>/dev/null || true

# Remove test artifacts
clean-test:
	@echo "Cleaning test artifacts..."
	@rm -rf .pytest_cache/ 2>/dev/null || true
	@rm -rf .coverage 2>/dev/null || true
	@rm -rf htmlcov/ 2>/dev/null || true
	@rm -rf .tox/ 2>/dev/null || true
	@rm -rf .cache/ 2>/dev/null || true
	@find . -name '.coverage.*' -delete 2>/dev/null || true

# Deep clean - everything
clean-all: clean-pyc clean-build clean-test
	@echo "Deep cleaning..."
	@rm -rf .mypy_cache/ 2>/dev/null || true
	@rm -rf .ruff_cache/ 2>/dev/null || true
	@rm -rf .uv/ 2>/dev/null || true
	@rm -rf node_modules/ 2>/dev/null || true
	@find . -name '.DS_Store' -delete 2>/dev/null || true
	@find . -name 'Thumbs.db' -delete 2>/dev/null || true
	@find . -name '*.log' -delete 2>/dev/null || true
	@find . -name '*.tmp' -delete 2>/dev/null || true
	@find . -name '*~' -delete 2>/dev/null || true
	@echo "Deep clean complete."

# Install package
install:
	@echo "Installing package..."
	pip install .

# Install package in development mode
dev-install:
	@echo "Installing package in development mode..."
	pip install -e .

# Run tests
test:
	@echo "$(BLUE)Running tests...$(NC)"
	@if command -v uv >/dev/null 2>&1; then \
		uv run pytest; \
	elif command -v pytest >/dev/null 2>&1; then \
		pytest; \
	else \
		python -m pytest; \
	fi

# Generate test coverage report
coverage:
	@echo "$(BLUE)Generating coverage report...$(NC)"
	@if command -v uv >/dev/null 2>&1; then \
		uv run pytest tests/ --cov=src/chuk_mcp_runtime --cov-report=html --cov-report=term --cov-report=xml; \
	else \
		pytest tests/ --cov=src/chuk_mcp_runtime --cov-report=html --cov-report=term --cov-report=xml; \
	fi
	@echo "$(GREEN)✓ Coverage report generated$(NC)"
	@echo "  HTML report: htmlcov/index.html"
	@echo "  XML report:  coverage.xml"

# Open coverage HTML report
coverage-html: coverage
	@echo "$(BLUE)Opening coverage report...$(NC)"
	@open htmlcov/index.html 2>/dev/null || xdg-open htmlcov/index.html 2>/dev/null || echo "Please open htmlcov/index.html manually"

# Legacy alias for coverage
test-cov: coverage

# Run the server launcher
run:
	@echo "Running server..."
	@if command -v uv >/dev/null 2>&1; then \
		PYTHONPATH=src uv run python -m chuk_protocol_server.server_launcher; \
	else \
		PYTHONPATH=src python3 -m chuk_protocol_server.server_launcher; \
	fi

# Build the project using the pyproject.toml configuration
build: clean-build
	@echo "Building project..."
	@if command -v uv >/dev/null 2>&1; then \
		uv build; \
	else \
		python3 -m build; \
	fi
	@echo "Build complete. Distributions are in the 'dist' folder."

# Publish the package to PyPI using twine
publish: build
	@echo "Publishing package..."
	@if [ ! -d "dist" ] || [ -z "$$(ls -A dist 2>/dev/null)" ]; then \
		echo "Error: No distribution files found. Run 'make build' first."; \
		exit 1; \
	fi
	@last_build=$$(ls -t dist/*.tar.gz dist/*.whl 2>/dev/null | head -n 2); \
	if [ -z "$$last_build" ]; then \
		echo "Error: No valid distribution files found."; \
		exit 1; \
	fi; \
	echo "Uploading: $$last_build"; \
	twine upload $$last_build
	@echo "Publish complete."

# Publish to test PyPI
publish-test: build
	@echo "Publishing to test PyPI..."
	@last_build=$$(ls -t dist/*.tar.gz dist/*.whl 2>/dev/null | head -n 2); \
	if [ -z "$$last_build" ]; then \
		echo "Error: No valid distribution files found."; \
		exit 1; \
	fi; \
	echo "Uploading to test PyPI: $$last_build"; \
	twine upload --repository testpypi $$last_build

# Check code quality
lint:
	@echo "Running linters..."
	@if command -v uv >/dev/null 2>&1; then \
		uv run ruff check .; \
		uv run ruff format --check .; \
	elif command -v ruff >/dev/null 2>&1; then \
		ruff check .; \
		ruff format --check .; \
	else \
		echo "Ruff not found. Install with: pip install ruff"; \
	fi

# Fix code formatting
format:
	@echo "Formatting code..."
	@if command -v uv >/dev/null 2>&1; then \
		uv run ruff format .; \
		uv run ruff check --fix .; \
	elif command -v ruff >/dev/null 2>&1; then \
		ruff format .; \
		ruff check --fix .; \
	else \
		echo "Ruff not found. Install with: pip install ruff"; \
	fi

# Type checking
typecheck:
	@echo "Running type checker..."
	@if command -v uv >/dev/null 2>&1; then \
		uv run mypy src; \
	elif command -v mypy >/dev/null 2>&1; then \
		mypy src; \
	else \
		echo "MyPy not found. Install with: pip install mypy"; \
	fi

# Run all checks
check: lint typecheck test
	@echo "All checks completed."

# Show project info
info:
	@echo "Project Information:"
	@echo "==================="
	@if [ -f "pyproject.toml" ]; then \
		echo "pyproject.toml found"; \
		if command -v uv >/dev/null 2>&1; then \
			echo "UV version: $$(uv --version)"; \
		fi; \
		if command -v python >/dev/null 2>&1; then \
			echo "Python version: $$(python --version)"; \
		fi; \
	else \
		echo "No pyproject.toml found"; \
	fi
	@echo "Current directory: $$(pwd)"
	@echo "Git status:"
	@git status --porcelain 2>/dev/null || echo "Not a git repository"
