.PHONY: clean data lint requirements sync_data_to_s3 sync_data_from_s3 simulate build marts quality stats results report app sensitivity pipeline

#################################################################################
# GLOBALS                                                                       #
#################################################################################

PROJECT_DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
BUCKET = [OPTIONAL] your-bucket-for-syncing-data (do not include 's3://')
PROFILE = default
PROJECT_NAME = checkout-flow-optimization
PYTHON_INTERPRETER = python3

ifeq (,$(shell which conda))
HAS_CONDA=False
else
HAS_CONDA=True
endif

#################################################################################
# COMMANDS                                                                      #
#################################################################################

## Install Python Dependencies
requirements: test_environment
	$(PYTHON_INTERPRETER) -m pip install -U pip setuptools wheel
	$(PYTHON_INTERPRETER) -m pip install -r requirements.txt

## Make Dataset
data: requirements
	$(PYTHON_INTERPRETER) src/data/make_dataset.py data/raw data/processed

## Delete all compiled Python files, generated data, and DuckDB files
clean:
	@echo "Cleaning project..."
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf data/raw/*
	rm -rf data/quarantine/*
	rm -f duckdb/warehouse.duckdb duckdb/warehouse.duckdb.wal
	rm -f reports/figures/*.csv reports/figures/*.png
	@echo "Clean complete! Removed generated data and DuckDB files"

## Lint using flake8
lint:
	flake8 src

## Upload Data to S3
sync_data_to_s3:
ifeq (default,$(PROFILE))
	aws s3 sync data/ s3://$(BUCKET)/data/
else
	aws s3 sync data/ s3://$(BUCKET)/data/ --profile $(PROFILE)
endif

## Download Data from S3
sync_data_from_s3:
ifeq (default,$(PROFILE))
	aws s3 sync s3://$(BUCKET)/data/ data/
else
	aws s3 sync s3://$(BUCKET)/data/ data/ --profile $(PROFILE)
endif

## Set up python interpreter environment
create_environment:
ifeq (True,$(HAS_CONDA))
		@echo ">>> Detected conda, creating conda environment."
ifeq (3,$(findstring 3,$(PYTHON_INTERPRETER)))
	conda create --name $(PROJECT_NAME) python=3
else
	conda create --name $(PROJECT_NAME) python=2.7
endif
		@echo ">>> New conda env created. Activate with:\nsource activate $(PROJECT_NAME)"
else
	$(PYTHON_INTERPRETER) -m pip install -q virtualenv virtualenvwrapper
	@echo ">>> Installing virtualenvwrapper if not already installed.\nMake sure the following lines are in shell startup file\n\
	export WORKON_HOME=$$HOME/.virtualenvs\nexport PROJECT_HOME=$$HOME/Devel\nsource /usr/local/bin/virtualenvwrapper.sh\n"
	@bash -c "source `which virtualenvwrapper.sh`;mkvirtualenv $(PROJECT_NAME) --python=$(PYTHON_INTERPRETER)"
	@echo ">>> New virtualenv created. Activate with:\nworkon $(PROJECT_NAME)"
endif

## Test python environment is setup correctly
test_environment:
	$(PYTHON_INTERPRETER) test_environment.py

#################################################################################
# PROJECT RULES                                                                 #
#################################################################################

## Generate synthetic checkout funnel data (4 days, 10k users/day)
simulate:
	@echo "Starting data simulation..."
	@source .venv/bin/activate && python src/data/simulate.py \
		--start 2025-01-01 \
		--days 4 \
		--users 10000 \
		--uplift 0.02 \
		--seed 7
	@echo ""
	@echo "Simulation complete! Data written to: $(PROJECT_DIR)/data/raw"

## Build DuckDB schema and register event views
build:
	@echo "Building DuckDB schema..."
	@source .venv/bin/activate && python -c "import duckdb; conn = duckdb.connect(); conn.execute(open('sql/schema.sql').read()); conn.close()"
	@echo "Schema built successfully! Database: $(PROJECT_DIR)/duckdb/warehouse.duckdb"

## Build analytical mart tables
marts:
	@echo "Building analytical marts..."
	@source .venv/bin/activate && python -c "import duckdb; conn = duckdb.connect(); \
		conn.execute(open('sql/marts/fct_experiments.sql').read()); \
		conn.execute(open('sql/marts/fct_checkout_steps.sql').read()); \
		conn.execute(open('sql/marts/fct_orders.sql').read()); \
		conn.close()"
	@echo "Marts built successfully! Tables: fct_experiments, fct_checkout_steps, fct_orders"

## Run data quality checks
quality:
	@source .venv/bin/activate && python src/quality.py && echo "" && echo "All data quality checks passed!"

## Run statistical analysis on most recent date
stats:
	@source .venv/bin/activate && python src/analysis/run_stats.py && echo "" && echo "Statistical analysis complete!"

## Save statistical results to JSON and CSV files
results:
	@source .venv/bin/activate && python src/analysis/save_results.py && echo "Results saved to: $(PROJECT_DIR)/reports/results"

## Generate compact markdown report with primary metric and guardrails
report:
	@echo "Generating report..."
	@source .venv/bin/activate && python src/report.py

## Launch Streamlit dashboard
app:
	@echo "Launching Streamlit dashboard..."
	@echo "Local URL: http://localhost:8501"
	@source .venv/bin/activate && streamlit run src/dashboard.py --server.port 8501 --server.headless true

## Run sensitivity analysis to compute CCR detection rates across parameter grid
sensitivity:
	@echo "Running sensitivity analysis..."
	@source .venv/bin/activate && python src/analysis/sensitivity.py \
		--start 2025-02-01 \
		--days 1 \
		--users "20000,50000" \
		--uplifts "0.0,0.02" \
		--repeats 10 \
		--seed 7
	@echo "Sensitivity results saved to: $(PROJECT_DIR)/reports/results/sensitivity_summary.csv"

## Run complete analysis pipeline from data generation to final report
pipeline: simulate build marts quality results report
	@echo ""
	@echo "================================================================================"
	@echo "PIPELINE COMPLETE!"
	@echo "================================================================================"
	@echo "Final report available at: $(PROJECT_DIR)/reports/REPORT.md"
	@echo "================================================================================"

#################################################################################
# Self Documenting Commands                                                     #
#################################################################################

.DEFAULT_GOAL := help

# Inspired by <http://marmelab.com/blog/2016/02/29/auto-documented-makefile.html>
# sed script explained:
# /^##/:
# 	* save line in hold space
# 	* purge line
# 	* Loop:
# 		* append newline + line to hold space
# 		* go to next line
# 		* if line starts with doc comment, strip comment character off and loop
# 	* remove target prerequisites
# 	* append hold space (+ newline) to line
# 	* replace newline plus comments by `---`
# 	* print line
# Separate expressions are necessary because labels cannot be delimited by
# semicolon; see <http://stackoverflow.com/a/11799865/1968>
.PHONY: help
help:
	@echo "$$(tput bold)Available rules:$$(tput sgr0)"
	@echo
	@sed -n -e "/^## / { \
		h; \
		s/.*//; \
		:doc" \
		-e "H; \
		n; \
		s/^## //; \
		t doc" \
		-e "s/:.*//; \
		G; \
		s/\\n## /---/; \
		s/\\n/ /g; \
		p; \
	}" ${MAKEFILE_LIST} \
	| LC_ALL='C' sort --ignore-case \
	| awk -F '---' \
		-v ncol=$$(tput cols) \
		-v indent=19 \
		-v col_on="$$(tput setaf 6)" \
		-v col_off="$$(tput sgr0)" \
	'{ \
		printf "%s%*s%s ", col_on, -indent, $$1, col_off; \
		n = split($$2, words, " "); \
		line_length = ncol - indent; \
		for (i = 1; i <= n; i++) { \
			line_length -= length(words[i]) + 1; \
			if (line_length <= 0) { \
				line_length = ncol - indent - length(words[i]) - 1; \
				printf "\n%*s ", -indent, " "; \
			} \
			printf "%s ", words[i]; \
		} \
		printf "\n"; \
	}' \
	| more $(shell test $(shell uname) = Darwin && echo '--no-init --raw-control-chars')
