# Procura — End-to-End Purchase Management System

A synthetic procurement workflow demo built with Python, Streamlit, pandas, and SQLite. It covers request intake, approvals, RFQs, supplier quote comparison, supplier award, purchase orders, delivery receipts, audit history, and exception monitoring.

## Main features

- Create purchase requests with item lines and budget/department checks.
- Approval queue with a configurable illustrative threshold and self-approval prevention.
- RFQ creation for approved requests; competitive RFQs require at least three valid quotes before award.
- Supplier quote capture and comparison by total landed cost (subtotal + shipping + tax), with lead time as a tie-breaker.
- PO and PO-line generation from the selected quote; budget reservation is updated.
- Delivery/receipt event capture including partial receipt, delay, and damaged-goods notes.
- Append-only interactive audit log and seeded workflow-event history.
- Exceptions derived from operational facts, without reading `ground_truth.csv`.
- Deterministic synthetic dataset and separate evaluation metadata.

## Requirements

- Python 3.10+
- Windows, macOS, or Linux

## Run locally (Windows PowerShell)

From the project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open the local URL printed by Streamlit (usually `http://localhost:8501`). The app seeds `data/workflow_app.db` on first launch from `data/generated/*.csv`. It intentionally excludes `ground_truth.csv` and `ground_truth.json` from operational tables. Delete only `data/workflow_app.db` if you want to rebuild the app's local demo database; the generated CSV files are not changed by normal app actions.

## Generate data and validate

The default fixed seed is `20261022`.

```powershell
python generator.py --out data/generated --seed 20261022
python validate_data.py --data data/generated
python -m pytest -q
```

Use `--scale 0.1` for a smaller deterministic starter dataset:

```powershell
python generator.py --out data/starter --seed 20261022 --scale 0.1
python validate_data.py --data data/starter
```

The generator writes CSV and JSON exports, `seed_data.sql`, and `manifest.json`. `schema.sql` defines the operational relational schema; apply it before `data/generated/seed_data.sql` when loading a SQL database. The SQL seed deliberately excludes ground-truth labels. Evaluation labels are in `data/generated/ground_truth.csv` and `ground_truth.json` only.

## Baseline volume

The full generator produces 300 requesters, 120 suppliers, 1,200 baseline purchase requests plus one labelled duplicate request, 500 RFQs, 1,500 supplier quotes, and 900 purchase orders. The 1,201 request rows are intentional because ANOM-06 is an additional duplicate fixture.

## Business rules (illustrative)

- Request estimates above INR 10,000 require an approval decision.
- RFQs are created only for approved requests.
- Competitive RFQs require at least three valid, unexpired, currency-matching quotes from active suppliers.
- Quote ranking uses landed cost, then lead time as a tie-breaker.
- New awards are blocked if the quote is expired, the supplier is inactive, currency does not match, or the available budget is insufficient.
- Purchase-order values are copied from the awarded quote; deliveries are explicit events.
- Each interactive state change writes an audit entry and a workflow event.

These are demo rules and should be adapted to a real organization's policy before production use.

## Ground truth and anomaly evaluation

`ground_truth.csv` and `ground_truth.json` are evaluation metadata, not operational input features. The app does not load them and does not use labels to drive approvals, supplier selection, PO creation, or exception decisions. The validator reads ground truth only to check whether the labelled edge cases exist in the generated operational records.

Seven fixtures are provided: PO without approval, quote expired before award, selected quote not cheapest with no rationale, inactive supplier, budget overrun, duplicate request, and quote/request currency mismatch. Some warnings are expected because these deliberately seeded cases are meant to be caught and reported by validation.

## Data model and deliverables

See `DATA_MODEL.md`, `data_dictionary.csv`, `schema.sql`, and `data/generated/manifest.json`. IDs are deterministic and zero-padded. The data is synthetic; no real personal or confidential data is used.

## Tests

```powershell
python -m pytest -q
```

Tests cover deterministic generation, required counts/fixtures, validator behavior, and basic workflow actions. Passing tests are a useful check, not a substitute for manually exercising the app before submission.

## Limitations

This is a portfolio assessment demo, not a production platform. It does not implement enterprise authentication, role-based permissions, migrations, concurrency locking, attachment handling, or production-grade accounting. The app DB is initialized from generated synthetic records, and the SQL schema/seed are provided as reproducible exports.

## Publish to a public GitHub repository

1. Create a new **Public** repository on GitHub (do not initialize it with a README if you already have this project locally).
2. Open PowerShell in this project folder and run the following, replacing the URL with your repository URL:

```powershell
git init
git add .
git commit -m "Submit procurement workflow project"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

3. Open the repository page in a private/incognito browser window to verify it is public and that `README.md`, source files, tests, schema, dictionary, and generated data are visible.
4. Run the validation and tests one last time, then submit the repository URL in the YottaFlex application. Submission is final according to the provided instructions, so double-check the URL before sending it.
