.PHONY: install install-embeddings test eval run-viewer fmt lint

install:
	pip install -e ".[dev]"

install-embeddings:
	pip install -e ".[embeddings]"

test:
	pytest -q --cov=papertriage --cov-report=term-missing

eval:
	python -m papertriage.eval

run-viewer:
	streamlit run viewer/app.py --server.headless=true

fmt:
	ruff format src/ tests/

lint:
	ruff check src/ tests/
