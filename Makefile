.PHONY: help build publish test clean install

help:
	@echo "x402-langchain build targets:"
	@echo "  make install   - Install the package in development mode"
	@echo "  make build     - Build distribution packages (wheel + sdist)"
	@echo "  make test      - Run pytest test suite"
	@echo "  make publish   - Upload built packages to PyPI (requires twine)"
	@echo "  make clean     - Remove build artifacts and cache files"

install:
	pip install -e .

build:
	python -m build

test:
	pytest

publish:
	twine upload dist/*

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
