.PHONY: lint.dryrun
lint.dryrun:
	@uv run ruff check .
	@uv run mypy .

.PHONY: lint
lint:
	@uv run ruff check --fix .
	@uv run mypy .
	@uv run ruff format .

.PHONY: test
test:
	@uv run python -m unittest discover -s tests
