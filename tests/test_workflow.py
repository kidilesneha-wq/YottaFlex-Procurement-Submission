import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import workflow
from generator import generate
from validate_data import validate


def test_generation_counts_validation_and_ground_truth_separation(tmp_path):
    out = tmp_path / "generated"
    manifest = generate(out, seed=20261022, scale=1.0)
    assert manifest["actual_row_counts"]["requesters.csv"] == 300
    assert manifest["actual_row_counts"]["suppliers.csv"] == 120
    assert manifest["actual_row_counts"]["purchase_requests.csv"] == 1201
    assert manifest["actual_row_counts"]["rfqs.csv"] == 500
    assert manifest["actual_row_counts"]["supplier_quotes.csv"] == 1500
    assert manifest["actual_row_counts"]["purchase_orders.csv"] == 900
    result = validate(out)
    assert result["valid"], result["errors"]
    assert all(v["valid"] for v in result["anomaly_checks"].values())
    assert (out / "ground_truth.json").exists()
    sql = (out / "seed_data.sql").read_text(encoding="utf-8")
    assert "INSERT INTO ground_truth" not in sql
    assert "ground_truth_separate" in json.loads((out / "manifest.json").read_text())


def test_seed_reproducibility(tmp_path):
    a = generate(tmp_path / "a", seed=123, scale=0.1)
    b = generate(tmp_path / "b", seed=123, scale=0.1)
    assert a["sha256"] == b["sha256"]


def test_sql_seed_imports_against_schema(tmp_path):
    out = tmp_path / "generated"
    generate(out, seed=20261022, scale=0.1)
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
    con.executescript((out / "seed_data.sql").read_text(encoding="utf-8"))
    assert con.execute("SELECT COUNT(*) FROM requesters").fetchone()[0] == 30
    assert con.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0] == 12
    assert con.execute("SELECT COUNT(*) FROM ground_truth").fetchone()[0] == 0 if "ground_truth" in [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")] else True
    con.close()


def test_basic_operational_workflow(tmp_path, monkeypatch):
    out = tmp_path / "generated"
    generate(out, seed=20261022, scale=0.1)
    monkeypatch.setattr(workflow, "DATA_DIR", out)
    monkeypatch.setattr(workflow, "DB_PATH", tmp_path / "app.db")
    workflow.initialize_db()
    requesters = workflow.frame("requesters")
    budgets = workflow.frame("budgets")
    requester = requesters.iloc[0]
    budget = budgets[budgets["department_id"].astype(str) == str(requester["department_id"])].iloc[0]
    request_id = workflow.create_request(str(requester["requester_id"]), str(budget["budget_id"]),
                                         "Test monitor", 2, 1000, (date.today()+timedelta(days=10)).isoformat(),
                                         "Testing procurement workflow")
    assert request_id.startswith("PR-2026-")
    rfq_id = workflow.create_rfq(request_id, (date.today()+timedelta(days=7)).isoformat(), competitive=False)
    suppliers = workflow.frame("suppliers")
    supplier = suppliers[suppliers["active"].astype(str).str.lower().isin(["true", "1", "yes", "active"])].iloc[0]
    quote_id = workflow.add_quote(rfq_id, str(supplier["supplier_id"]), (date.today()+timedelta(days=14)).isoformat(),
                                  2000, 0, 360, 5, "INR")
    po_id = workflow.award_quote(rfq_id, quote_id)
    delivery_id = workflow.record_delivery(po_id, 2, "delivered", "All items received")
    assert po_id.startswith("PO-2026-")
    assert delivery_id.startswith("DEL-")
    assert workflow.frame("audit_log").shape[0] >= 4
    assert workflow.frame("purchase_orders").query("po_id == @po_id")["status"].iloc[0] == "received"


def test_exception_report_uses_operational_facts_not_ground_truth(tmp_path, monkeypatch):
    out = tmp_path / "generated"
    generate(out, seed=20261022, scale=0.1)
    monkeypatch.setattr(workflow, "DATA_DIR", out)
    monkeypatch.setattr(workflow, "DB_PATH", tmp_path / "app.db")
    workflow.initialize_db()
    exceptions = workflow.exception_report()
    types = set(exceptions["type"].astype(str))
    assert "PO without approval" in types
    assert "Expired quote awarded" in types
    assert "Non-cheapest quote without rationale" in types
    assert "Inactive supplier awarded" in types
    assert "Budget overrun" in types
    assert "Currency mismatch" in types
    assert "Duplicate request candidate" in types
    with workflow.connect() as con:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "ground_truth" not in tables
