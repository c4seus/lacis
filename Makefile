PYTHON ?= python

.PHONY: install lint format types test coverage check

install:
	$(PYTHON) -m pip install -e ".[dev]"

lint:
	ruff check .
	ruff format --check .
	$(PYTHON) scripts/check_no_comments.py

format:
	ruff check --fix .
	ruff format .

types:
	mypy

test:
	QT_QPA_PLATFORM=offscreen pytest

coverage:
	QT_QPA_PLATFORM=offscreen pytest --cov --cov-report=term

check: lint types coverage
