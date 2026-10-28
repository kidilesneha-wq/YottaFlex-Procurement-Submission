# YottaFlex Procurement Management System

A Python and Streamlit application for managing procurement requests, approvals, supplier quotes, purchase orders, deliveries, and exception reporting.

## Features

- Procurement workflow dashboard
- Purchase request and approval management
- Supplier quote comparison
- Purchase order and delivery tracking
- Synthetic data generation
- Business-rule validation and anomaly reporting
- Workflow event tracking and audit history
- Automated tests

## Requirements

Python 3.10 or newer is recommended.

## Installation

Open PowerShell in the project directory and run:

```powershell
python -m pip install -r requirements.txt
```

## Generate the dataset

```powershell
python generator.py --out data/generated --seed 20261022
```

## Validate the dataset

```powershell
python validate_data.py --data data/generated
```

## Run the application

```powershell
python -m streamlit run app.py
```

Open the local URL displayed in the terminal.

## Run automated tests

```powershell
python -m pytest -q
```

The project tests previously passed with five tests. Run the command above to verify the current version.

## Project structure

- `app.py` — Streamlit dashboard
- `workflow.py` — procurement workflow logic
- `generator.py` — deterministic synthetic data generator
- `validate_data.py` — dataset validation
- `schema.sql` — relational database schema
- `data_dictionary.csv` — field definitions
- `DATA_MODEL.md` — data model documentation
- `tests/test_workflow.py` — automated tests
- `data/generated/` — generated CSV, JSON, and SQL files

## Business rules

- Requests above INR 10,000 require an approval decision.
- RFQs are created only for approved requests.
- Competitive RFQs require at least three valid quotes from active suppliers.
- Supplier selection considers landed cost and delivery lead time.
- Expired quotes, inactive suppliers, currency mismatches, and budget overruns are exception conditions.
- Workflow actions are recorded for traceability.

These are illustrative assessment rules and should be adapted before production use.

## Synthetic data and anomaly fixtures

The dataset contains synthetic procurement records and seven labelled anomaly fixtures for evaluation. Ground-truth labels are evaluation metadata and are not intended to drive operational decisions.

## Limitations

This is an assessment demo, not a production procurement platform. It does not implement enterprise authentication, role-based access control, database migrations, concurrency locking, or production-grade accounting.
