TOP_DIR := .
TEST_DIR := $(TOP_DIR)/tests
DIST_DIR := $(TOP_DIR)/dist
REQUIREMENTS_FILE := $(TOP_DIR)/requirements.txt
LIB_NAME := mcp_state_server
LIB_VERSION := $(shell grep -m 1 version pyproject.toml | tr -s ' ' | tr -d '"' | tr -d "'" | cut -d' ' -f3)
LIB := $(LIB_NAME)-$(LIB_VERSION)-py3-none-any.whl
TARGET := $(DIST_DIR)/$(LIB)

ifeq ($(OS),Windows_NT)
    PYTHON := py.exe
else
    PYTHON := python3
endif

UV := uv
SYNC := $(UV) sync 
BUILD := $(UV) build 
PYTHON := $(UV) run python 
EXPORT := $(UV) pip freeze --exclude-editable | grep -v -E "(databricks-vectorsearch|pyspark|databricks-connect|pytest|ruff|mypy|^uv==)" 
PUBLISH := $(UV) run twine upload
PYTEST := $(UV) run python -m pytest -v -s
RUFF_CHECK := $(UV) run ruff check --fix --ignore E501 
RUFF_FORMAT := $(UV) run ruff format 
FIND := $(shell which find)
RM := rm -rf
CD := cd

.PHONY: all clean distclean dist check format publish help test unit-test integration-test deploy-app deploy-bundle

all: dist

install: depends 
	$(SYNC) 

dist: install
	$(BUILD)

depends: 
	@$(SYNC) 
	@$(EXPORT) > $(REQUIREMENTS_FILE)

check: 
	$(RUFF_CHECK) mcp_state_server $(TEST_DIR) 

format: check depends
	$(RUFF_FORMAT) mcp_state_server $(TEST_DIR) 

publish: dist
	$(PUBLISH) $(DIST_DIR)/*

clean: 
	$(FIND) mcp_state_server $(TEST_DIR) -name \*.pyc -exec rm -f {} \;
	$(FIND) mcp_state_server $(TEST_DIR) -name \*.pyo -exec rm -f {} \;

distclean: clean
	$(RM) $(DIST_DIR)
	$(RM) mcp_state_server/*.egg-info 
	$(RM) $(TOP_DIR)/.mypy_cache
	$(FIND) mcp_state_server . $(TEST_DIR) app.py \( -name __pycache__ -a -type d \) -prune -exec rm -rf {} \;

test: 
	$(PYTEST) -ra --tb=short $(TEST_DIR)

unit-test:
	$(PYTEST) -ra --tb=short $(TEST_DIR)/unit

integration-test:
	$(PYTEST) -ra --tb=short $(TEST_DIR)/integration

deploy-app: dist
	@echo "Deploying as Databricks App..."
	@echo "Running deployment script..."
	@./deploy.sh

deploy-bundle: dist
	@echo "Deploying using Databricks Asset Bundles..."
	@echo "Make sure you have configured bundle variables:"
	@echo "  databricks bundle deploy --var postgres_instance_name=your-instance"
	databricks bundle deploy

help:
	$(info TOP_DIR: $(TOP_DIR))
	$(info TEST_DIR: $(TEST_DIR))
	$(info DIST_DIR: $(DIST_DIR))
	$(info )
	$(info $$> make [all|dist|install|clean|distclean|format|depends|publish|test|unit-test|integration-test|help])
	$(info )
	$(info       all              - build library: [$(LIB)]. This is the default)
	$(info       dist             - build library: [$(LIB)])
	$(info       install          - installs: [$(LIB)])
	$(info       clean            - removes build artifacts)
	$(info       distclean        - removes library)
	$(info       format           - format source code)
	$(info       depends          - installs library dependencies)
	$(info       publish          - publish library)
	$(info       test             - run all tests)
	$(info       unit-test        - run unit tests only)
	$(info       integration-test - run integration tests only)
	$(info       deploy-app       - deploy as Databricks App)
	$(info       deploy-bundle    - deploy using Asset Bundles)
	$(info       help             - show this help message)
	@true

