"""Deterministic synthetic procurement data generator.

Usage:
  python generator.py --out data/generated --seed 20261022
  python generator.py --out data/generated --seed 20261022 --scale 0.1

WARNING: This overwrites CSV/JSON files in the selected output directory.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, random
from pathlib import Path
from datetime import date, timedelta

BASE = {"requesters": 300, "suppliers": 120, "requests": 1200,
        "rfqs": 500, "quotes": 1500, "purchase_orders": 900}
DEPARTMENT_NAMES = ["Engineering", "IT", "Finance", "HR", "Operations", "Sales",
                    "Marketing", "Support", "Legal", "Facilities"]

def write_csv(path: Path, rows):
    rows = list(rows)
    if not rows:
        path.write_text("", encoding="utf-8")
        return 0
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    return len(rows)

def generate(out_dir="data/generated", seed=20261022, scale=1.0):
    if scale <= 0: raise ValueError("scale must be > 0")
    rng = random.Random(seed); out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    n = {k: max(1, int(v * scale)) for k, v in BASE.items()}
    # Keep the requested ratio of 3 quotes per RFQ at all scales.
    n["quotes"] = n["rfqs"] * 3
    today = date(2026, 10, 22)

    departments = [{"department_id": f"DEPT-{i:03}", "name": name,
                    "cost_center": f"CC-{i:03}"}
                   for i, name in enumerate(DEPARTMENT_NAMES, 1)]
    budgets = [{"budget_id": f"BUD-{i:03}-2026", "department_id": departments[(i-1)%len(departments)]["department_id"],
                "fiscal_year": 2026, "currency": "INR", "allocated_amount": 2500000 + i*150000,
                "reserved_amount": 0, "spent_amount": 0}
               for i in range(1, len(departments)+1)]
    requesters = [{"requester_id": f"USR-{i:04}", "name": f"Requester {i:04}",
                   "email": f"requester{i:04}@example.test",
                   "department_id": departments[(i-1)%len(departments)]["department_id"], "active": "true"}
                  for i in range(1, n["requesters"]+1)]
    suppliers = [{"supplier_id": f"SUP-{i:04}", "supplier_code": f"S{i:04}",
                  "name": f"Supplier {i:04}", "currency": "INR",
                  "active": "false" if i == 7 else "true",
                  "risk_flag": "high" if i in (11, 23) else "none",
                  "payment_terms_days": rng.choice([15, 30, 45, 60])}
                 for i in range(1, n["suppliers"]+1)]

    requests, request_lines = [], []
    for i in range(1, n["requests"]+1):
        created = today - timedelta(days=rng.randint(20, 250))
        requester = requesters[(i-1) % len(requesters)]
        estimate = rng.randint(1200, 65000)
        requests.append({"request_id": f"PR-2026-{i:06}", "requester_id": requester["requester_id"],
            "department_id": requester["department_id"], "budget_id": budgets[(i-1)%len(budgets)]["budget_id"],
            "created_date": created.isoformat(), "needed_by_date": (created+timedelta(days=rng.randint(7,45))).isoformat(),
            "currency": "INR", "status": "approved" if i % 5 else "pending",
            "estimated_total": estimate, "business_purpose": f"Operational purchase {i:04}"})
        qty = rng.randint(1, 12)
        request_lines.append({"request_line_id": f"PRL-{i:06}-01", "request_id": f"PR-2026-{i:06}",
            "line_number": 1, "item_code": f"ITEM-{i%80+1:03}", "description": f"Procurement item {i%80+1:03}",
            "quantity": qty, "unit": "each", "estimated_unit_price": round(estimate/qty,2), "currency": "INR"})

    eligible = [r for r in requests if r["status"] == "approved"]
    rfqs = []
    for i in range(1, n["rfqs"]+1):
        req = eligible[(i-1) % len(eligible)]
        issued = date.fromisoformat(req["created_date"]) + timedelta(days=1)
        rfqs.append({"rfq_id": f"RFQ-2026-{i:06}", "request_id": req["request_id"],
            "issued_date": issued.isoformat(), "due_date": (issued+timedelta(days=7)).isoformat(),
            "status": "awarded", "competitive": "true", "currency": "INR"})

    quotes = []
    active_suppliers = [supplier for supplier in suppliers if supplier["active"] == "true"]
    # Exactly three quotes per RFQ from active suppliers in the baseline. The
    # inactive-supplier exception is injected explicitly into ANOM-04 later.
    for i in range(1, n["quotes"]+1):
        rfq = rfqs[(i-1)//3]
        supplier = active_suppliers[(i-1) % len(active_suppliers)]
        received = date.fromisoformat(rfq["issued_date"]) + timedelta(days=2+(i%4))
        subtotal = 10000 + (i*7919) % 40000
        shipping = (i%11)*250
        quotes.append({"quote_id": f"QUO-{supplier['supplier_code']}-2026-{i:06}", "rfq_id": rfq["rfq_id"],
            "supplier_id": supplier["supplier_id"], "received_date": received.isoformat(),
            "expiry_date": (received+timedelta(days=14)).isoformat(), "currency": "INR",
            "subtotal": subtotal, "shipping": shipping, "tax": round(subtotal*0.18,2),
            "lead_time_days": 3+i%24, "status": "submitted"})

    approvals = [{"approval_id": f"APR-{i:06}-01", "request_id": req["request_id"],
        "approver_id": f"APRVR-{i%20+1:03}", "decision": "approved", "decision_date": req["created_date"],
        "threshold_rule": "manager_review" if float(req["estimated_total"]) > 10000 else "standard"}
        for i, req in enumerate(requests, 1) if req["status"] == "approved"]

    # Ensure the seeded partial-delivery case has at least two ordered units.
    partial_request_id = rfqs[5]["request_id"] if len(rfqs) >= 6 else None
    if partial_request_id:
        partial_line = next((x for x in request_lines if x["request_id"] == partial_request_id), None)
        partial_req = next((x for x in requests if x["request_id"] == partial_request_id), None)
        if partial_line and partial_req and int(float(partial_line["quantity"])) < 2:
            partial_line["quantity"] = 2
            partial_line["estimated_unit_price"] = round(float(partial_req["estimated_total"])/2, 2)

    pos, po_lines, deliveries, awards, events = [], [], [], [], []
    # Helpers to find RFQ requests and the 3 quotes for each RFQ.
    request_by_id = {r["request_id"]: r for r in requests}
    for i in range(1, n["purchase_orders"]+1):
        if i <= len(rfqs) or len(rfqs) <= 7:
            rfq = rfqs[(i-1) % len(rfqs)]
        else:
            # Extra POs represent split purchases against ordinary RFQs; avoid
            # reusing the seven specially seeded anomaly RFQs.
            rfq = rfqs[7 + ((i-len(rfqs)-1) % (len(rfqs)-7))]
        req = request_by_id[rfq["request_id"]]
        candidates = [q for q in quotes if q["rfq_id"] == rfq["rfq_id"]]
        po_date = date.fromisoformat(req["created_date"]) + timedelta(days=10)
        # Expiry anomaly is scoped to PO-000002; subsequent split POs must not
        # reuse that now-expired quote as their selected quote.
        if i > 7:
            valid_candidates = [q for q in candidates if date.fromisoformat(q["expiry_date"]) >= po_date]
            if valid_candidates:
                candidates = valid_candidates

        # Choose lowest landed-cost quote in the baseline.
        selected = min(candidates, key=lambda q: float(q["subtotal"])+float(q["shipping"])+float(q["tax"]))
        rationale = "Lowest valid landed cost among received quotes"
        if i == 3:  # selected quote not cheapest, with no documented rationale
            selected = max(candidates, key=lambda q: float(q["subtotal"])+float(q["shipping"])+float(q["tax"]))
            rationale = ""
        elif i == 4:  # inactive supplier anomaly, but keep quote/PO supplier consistent
            selected = candidates[0]
            selected["supplier_id"] = "SUP-0007"
            selected["quote_id"] = f"QUO-S0007-2026-{int(selected['quote_id'].rsplit('-', 1)[1]):06}"
            # Make this selected quote the cheapest among its RFQ's alternatives.
            for other in candidates:
                if other is not selected:
                    other["subtotal"] = max(int(other["subtotal"]), int(selected["subtotal"])+10000)
                    other["tax"] = round(float(other["subtotal"])*0.18, 2)
            rationale = "Lowest valid landed cost among received quotes"
        elif i == 5:  # true budget overrun; PO remains equal to awarded quote total
            selected = candidates[0]
            selected["subtotal"] = 150000
            selected["tax"] = 27000
            selected["shipping"] = 250
            # Make the other quotes more expensive so the selected quote remains cheapest.
            for other in candidates:
                if other is not selected:
                    other["subtotal"] = max(int(other["subtotal"]), 200000)
                    other["tax"] = round(float(other["subtotal"])*0.18, 2)
            target_budget_id = req["budget_id"]
            for budget in budgets:
                if budget["budget_id"] == target_budget_id:
                    budget["allocated_amount"] = 100000
            rationale = "Lowest valid landed cost among received quotes"
        elif i == 7:  # quote currency differs from request currency
            selected = candidates[0]
            selected["currency"] = "USD"
            rationale = "Seeded currency mismatch for validation exercise"

        # Expired quote anomaly: persisted expiry date precedes award/PO date.
        if i == 2:
            selected["expiry_date"] = (po_date-timedelta(days=1)).isoformat()
        # PO without qualifying approval: remove approval for its request after creation below.
        if i == 1:
            approvals[:] = [a for a in approvals if a["request_id"] != req["request_id"]]

        total = round(float(selected["subtotal"])+float(selected["shipping"])+float(selected["tax"]), 2)
        po_id = f"PO-2026-{i:06}"
        pos.append({"po_id": po_id, "request_id": req["request_id"], "rfq_id": rfq["rfq_id"],
            "quote_id": selected["quote_id"], "supplier_id": selected["supplier_id"], "po_date": po_date.isoformat(),
            "currency": selected["currency"], "subtotal": selected["subtotal"], "shipping": selected["shipping"],
            "tax": selected["tax"], "total": total, "status": "partially_received" if i == 6 else "received",
            "selection_rationale": rationale})
        req_line = next((x for x in request_lines if x["request_id"] == req["request_id"]), None)
        if req_line:
            po_lines.append({"po_line_id": f"POL-{i:06}-01", "po_id": po_id,
                "request_line_id": req_line["request_line_id"], "description": req_line["description"],
                "quantity_ordered": req_line["quantity"], "unit_price": round(float(selected["subtotal"])/max(1,int(req_line["quantity"])),6),
                "currency": selected["currency"]})
        ordered_qty = int(float(req_line["quantity"])) if req_line else 1
        received_qty = max(1, ordered_qty - 1) if i == 6 else ordered_qty
        deliveries.append({"delivery_id": f"DEL-{po_id}-01", "po_id": po_id,
            "event_date": (po_date+timedelta(days=5)).isoformat(),
            "event_type": "partial_delivery" if i == 6 else "delivered", "quantity_received": received_qty,
            "quantity_expected": ordered_qty,
            "notes": "Partial delivery; balance pending" if i == 6 else "Delivery recorded"})
        awards.append({"po_id": po_id, "quote_id": selected["quote_id"], "supplier_id": selected["supplier_id"],
            "award_date": po_date.isoformat()})
        events.append({"event_id": f"EVT-{len(events)+1:07}", "entity_type": "purchase_order", "entity_id": po_id,
            "event_type": "purchase_order_issued", "event_date": po_date.isoformat(), "actor_id": "SYSTEM",
            "details": f"Generated from awarded quote {selected['quote_id']}"})

    # Duplicate request and matching line; IDs remain unique and references valid.
    duplicate = dict(requests[0]); duplicate["request_id"] = f"PR-2026-{n['requests']+1:06}"
    duplicate["business_purpose"] = requests[0]["business_purpose"] + " (duplicate anomaly)"
    requests_out = requests + [duplicate]
    first_line = next(x for x in request_lines if x["request_id"] == requests[0]["request_id"])
    duplicate_line = dict(first_line); duplicate_line["request_line_id"] = f"PRL-{n['requests']+1:06}-01"; duplicate_line["request_id"] = duplicate["request_id"]
    request_lines.append(duplicate_line)

    # Ground truth is generated from these documented, persisted fixtures.
    truth = [
      ("ANOM-01","purchase_order","PO-2026-000001","po_without_approval","No approval record exists for the request."),
      ("ANOM-02","purchase_order","PO-2026-000002","quote_expired_before_award","Award date is after quote expiry."),
      ("ANOM-03","purchase_order","PO-2026-000003","selected_quote_not_cheapest","Selected quote has higher landed cost and no documented rationale."),
      ("ANOM-04","purchase_order","PO-2026-000004","inactive_supplier","Selected supplier is inactive."),
      ("ANOM-05","purchase_order","PO-2026-000005","budget_overrun","PO total exceeds linked budget allocation."),
      ("ANOM-06","purchase_request",duplicate["request_id"],"duplicate_request","Matching requester, department, budget, dates and estimate."),
      ("ANOM-07","purchase_order","PO-2026-000007","quote_currency_mismatch","Selected quote currency differs from request currency.")]
    ground_truth = [dict(anomaly_id=a, entity_type=b, entity_id=c, label=d, expected_issue=e) for a,b,c,d,e in truth]

    # Event history for important generated lifecycle actions.
    for req in requests_out:
        events.append({"event_id": f"EVT-{len(events)+1:07}", "entity_type": "purchase_request", "entity_id": req["request_id"],
            "event_type": "request_created", "event_date": req["created_date"], "actor_id": req["requester_id"], "details": "Synthetic request created"})
    for approval in approvals:
        events.append({"event_id": f"EVT-{len(events)+1:07}", "entity_type": "purchase_request", "entity_id": approval["request_id"],
            "event_type": "approval_recorded", "event_date": approval["decision_date"], "actor_id": approval["approver_id"], "details": approval["decision"]})

    tables = {"departments.csv": departments, "budgets.csv": budgets, "requesters.csv": requesters,
      "suppliers.csv": suppliers, "purchase_requests.csv": requests_out, "request_lines.csv": request_lines,
      "rfqs.csv": rfqs, "supplier_quotes.csv": quotes, "approvals.csv": approvals,
      "purchase_orders.csv": pos, "purchase_order_lines.csv": po_lines, "deliveries.csv": deliveries,
      "awarded_quotes.csv": awards, "workflow_events.csv": events}
    counts = {name: write_csv(out/name, rows) for name, rows in tables.items()}
    write_csv(out/"ground_truth.csv", ground_truth)
    # JSON exports are generated from the same persisted records. Ground truth is
    # exported separately and is never included in operational seed SQL.
    for csv_path in sorted(out.glob("*.csv")):
        with csv_path.open(newline="", encoding="utf-8-sig") as f:
            records = list(csv.DictReader(f))
        (out / f"{csv_path.stem}.json").write_text(
            json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")

    # Produce an executable SQL seed script for operational tables only.
    operational = [name for name in tables if name != "ground_truth.csv"]
    def sql_value(value):
        if value is None: return "NULL"
        return "'" + str(value).replace("'", "''") + "'"
    sql_lines = ["-- Generated synthetic procurement seed data. Apply schema.sql first.",
                 "PRAGMA foreign_keys = ON;", "BEGIN TRANSACTION;"]
    for filename in operational:
        table = filename[:-4]
        rows = tables[filename]
        if not rows: continue
        cols = list(rows[0].keys())
        for row in rows:
            sql_lines.append(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join(sql_value(row.get(c)) for c in cols)});")
    sql_lines.extend(["COMMIT;", ""])
    (out / "seed_data.sql").write_text("\n".join(sql_lines), encoding="utf-8")

    checksums = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(out.glob("*.csv")) + [p for p in sorted(out.glob("*.json")) if p.name != "manifest.json"] + [out / "seed_data.sql"]}
    manifest = {"seed": seed, "scale": scale, "base_counts": n, "actual_row_counts": counts,
                "ground_truth_rows": len(ground_truth), "sha256": checksums, "synthetic_data": True,
                "ground_truth_separate": True, "sql_seed_excludes_ground_truth": True}
    (out/"manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--out", default="data/generated")
    parser.add_argument("--seed", type=int, default=20261022); parser.add_argument("--scale", type=float, default=1.0)
    args = parser.parse_args(); manifest = generate(args.out, args.seed, args.scale)
    print(json.dumps({"seed": manifest["seed"], "counts": manifest["actual_row_counts"],
                      "ground_truth_rows": manifest["ground_truth_rows"]}, indent=2))
if __name__ == "__main__": main()
