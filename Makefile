MODULE := seamm
.PHONY: help clean clean-build clean-docs clean-pyc clean-test lint format typing test
.PHONY: dependencies test-all coverage html docs servedocs release check-release
.PHONY: dist install uninstall
.DEFAULT_GOAL := help

define BROWSER_PYSCRIPT
import os, webbrowser, sys
try:
	from urllib import pathname2url
except:
	from urllib.request import pathname2url

webbrowser.open("file://" + pathname2url(os.path.abspath(sys.argv[1])))
endef

export BROWSER_PYSCRIPT

define PRINT_HELP_PYSCRIPT
import re, sys

for line in sys.stdin:
	match = re.match(r'^([a-zA-Z_-]+):.*?## (.*)$$', line)
	if match:
		target, help = match.groups()
		print("%-20s %s" % (target, help))
endef

export PRINT_HELP_PYSCRIPT

BROWSER := python -c "$$BROWSER_PYSCRIPT"

help:
	@python -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)

clean: clean-build clean-pyc clean-test ## remove all build, test, coverage and Python artifacts


clean-build: ## remove build artifacts
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

clean-pyc: ## remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

clean-test: ## remove test and coverage artifacts
	rm -fr .tox/
	rm -f .coverage
	rm -fr htmlcov/
	find . -name '.pytype' -exec rm -fr {} +

lint: ## check style with black and flake8
	black --extend-exclude '_version.py' --check --diff $(MODULE) tests
	flake8 --color never $(MODULE) tests

format: ## reformat with with yapf and isort
	black --extend-exclude '_version.py' $(MODULE) tests

test: ## run tests quickly with the default Python
	pytest tests/

coverage: ## check code coverage quickly with the default Python
	pytest -v --cov=$(MODULE) --cov-report term --color=yes tests/

coverage-html: ## check code coverage quickly with the default Python, showing as html
	pytest -v --cov=$(MODULE) --cov-report=html:htmlcov --cov-report term --color=yes tests/
	$(BROWSER) htmlcov/index.html

clean-docs: ## remove files associated with building the docs
	rm -f docs/api/$(MODULE).rst
	rm -f docs/api/modules.rst
	$(MAKE) -C docs clean

html: clean-docs ## generate Sphinx HTML documentation, including API docs
	sphinx-apidoc -o docs/api $(MODULE)
	$(MAKE) -C docs html
	rm -f docs/api/$(MODULE).rst
	rm -f docs/api/modules.rst

docs: html ## Make the html docs and show in the browser
	$(BROWSER) docs/_build/html/index.html

servedocs: docs ## compile the docs watching for changes
	watchmedo shell-command -p '*.rst' -c '$(MAKE) -C docs html' -R -D .

release: dist ## package and upload a release
	python -m twine upload dist/*

check-release: dist ## check the release for errors
	python -m twine check dist/*

dist: clean ## builds source and wheel package
	python -m build
	ls -l dist

install: uninstall ## install the package to the active Python's site-packages
	pip install .

uninstall: clean ## uninstall the package
	pip uninstall --yes $(MODULE)
