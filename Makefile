# fraiseql-seed Makefile
# Version management + PR workflow

.PHONY: help test lint typecheck check version-show version-patch version-minor version-major \
        pr-ship pr-ship-patch pr-ship-minor pr-ship-major pr-ship-no-version

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------

test: ## Run all tests
	uv run pytest --tb=short -q

lint: ## Run ruff lint + format check
	uv run ruff check
	uv run ruff format --check

typecheck: ## Run ty type checker
	uv run ty check

check: lint typecheck test ## Run all quality checks

# ---------------------------------------------------------------------------
# Version management
# ---------------------------------------------------------------------------

version-show: ## Show current version
	@python3 scripts/version_manager.py show

version-patch: ## Bump patch version (0.1.0 → 0.1.1)
	python3 scripts/version_manager.py patch

version-minor: ## Bump minor version (0.1.0 → 0.2.0)
	python3 scripts/version_manager.py minor

version-major: ## Bump major version (0.1.0 → 1.0.0)
	python3 scripts/version_manager.py major

# ---------------------------------------------------------------------------
# PR workflow
# ---------------------------------------------------------------------------

pr-ship: pr-ship-patch ## Ship PR with patch version bump (default)

pr-ship-patch: version-patch ## Bump patch + create PR → dev
	git add -A
	git commit -m "chore: bump version to $$(python3 scripts/version_manager.py show | cut -d' ' -f3)"
	git push -u origin HEAD
	gh pr create --base dev --fill

pr-ship-minor: version-minor ## Bump minor + create PR → dev
	git add -A
	git commit -m "chore: bump version to $$(python3 scripts/version_manager.py show | cut -d' ' -f3)"
	git push -u origin HEAD
	gh pr create --base dev --fill

pr-ship-major: version-major ## Bump major + create PR → dev
	git add -A
	git commit -m "chore: bump version to $$(python3 scripts/version_manager.py show | cut -d' ' -f3)"
	git push -u origin HEAD
	gh pr create --base dev --fill

pr-ship-no-version: ## Create PR → dev without version bump
	git push -u origin HEAD
	gh pr create --base dev --fill
