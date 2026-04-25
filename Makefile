.PHONY: install test eval run-viewer fmt lint

install:
	pip install -e ".[dev]"

test:
	pytest -q --cov=papertriage --cov-report=term-missing

eval:
	python -m papertriage.eval

run-viewer:
	streamlit run viewer/app.py

fmt:
	ruff format src/ tests/

lint:
	ruff check src/ tests/
