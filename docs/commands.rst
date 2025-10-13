Commands
========

The Makefile contains the central entry points for common tasks related to this project. All commands should be run from the project root directory.

Main Pipeline Commands
^^^^^^^^^^^^^^^^^^^^^^

* `make pipeline` - Run the complete analysis pipeline from data generation to final report. This is the main command that orchestrates the entire workflow: simulate → build → marts → quality → results → report.

* `make simulate` - Generate synthetic checkout funnel data (4 days, 10k users/day) with configurable treatment effects and store as partitioned Parquet files.

* `make build` - Build DuckDB schema and register event views over the raw Parquet data.

* `make marts` - Build analytical mart tables (fct_experiments, fct_checkout_steps, fct_orders) for fast analytical queries.

* `make quality` - Run data quality checks to validate data integrity, referential constraints, and business rules.

* `make stats` - Run statistical analysis on the most recent date, including two-proportion z-tests and confidence intervals.

* `make results` - Save statistical results to JSON and CSV files in the reports/results directory.

* `make report` - Generate a compact markdown report with primary metrics and guardrails.

* `make app` - Launch the Streamlit interactive dashboard at http://localhost:8501.

* `make sensitivity` - Run sensitivity analysis to compute CCR detection rates across parameter grids for power analysis.

Data Management Commands
^^^^^^^^^^^^^^^^^^^^^^^^

* `make data` - Process raw data into cleaned datasets (currently calls make_dataset.py).

* `make clean` - Delete all compiled Python files, generated data, and DuckDB files. Use this to reset the project to a clean state.

Development Commands
^^^^^^^^^^^^^^^^^^^^

* `make requirements` - Install Python dependencies from requirements.txt.

* `make lint` - Run flake8 linting on the src directory.

* `make test_environment` - Test that the Python environment is set up correctly.

Data Sync Commands
^^^^^^^^^^^^^^^^^^

* `make sync_data_to_s3` - Upload data to S3 using `aws s3 sync` to recursively sync files in `data/` up to the configured S3 bucket.

* `make sync_data_from_s3` - Download data from S3 using `aws s3 sync` to recursively sync files from the configured S3 bucket to `data/`.

Quick Start Workflow
^^^^^^^^^^^^^^^^^^^^

For a typical analysis session:

1. `make pipeline` - Run the complete analysis
2. `make app` - Launch the dashboard to explore results
3. `make sensitivity` - Run power analysis if needed
4. `make clean` - Clean up when done

All commands automatically activate the virtual environment and provide progress feedback.
