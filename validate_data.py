"""Structural, relational, financial, lifecycle and anomaly validation.
Run: python validate_data.py --data data/generated
"""
import argparse, csv, json
from pathlib import Path
from datetime import date

REQUIRED = {
 "departments.csv": ["department_id"], "budgets.csv": ["budget_id","department_id","allocated_amount"],
 "requesters.csv": ["requester_id","department_id"], "suppliers.csv": ["supplier_id","active"],
 "purchase_requests.csv": ["request_id","requester_id","department_id","budget_id","created_date","needed_by_date","currency","estimated_total"],
 "request_lines.csv": ["request_line_id","request_id","quantity","estimated_unit_price"],
 "rfqs.csv": ["rfq_id","request_id","issued_date","due_date"],
 "supplier_quotes.csv": ["quote_id","rfq_id","supplier_id","received_date","expiry_date","currency","subtotal","shipping","tax"],
 "approvals.csv": ["approval_id","request_id","decision"],
 "purchase_orders.csv": ["po_id","request_id","rfq_id","quote_id","supplier_id","po_date","subtotal","shipping","tax","total","currency"],
 "purchase_order_lines.csv": ["po_line_id","po_id","request_line_id"],
 "deliveries.csv": ["delivery_id","po_id","event_date"],
 "awarded_quotes.csv": ["po_id","quote_id","supplier_id","award_date"],
 "workflow_events.csv": ["event_id","entity_type","entity_id","event_type","event_date"],
 "ground_truth.csv": ["anomaly_id","entity_type","entity_id","label"]}
PK = {"departments.csv":"department_id","budgets.csv":"budget_id","requesters.csv":"requester_id","suppliers.csv":"supplier_id",
 "purchase_requests.csv":"request_id","request_lines.csv":"request_line_id","rfqs.csv":"rfq_id","supplier_quotes.csv":"quote_id",
 "approvals.csv":"approval_id","purchase_orders.csv":"po_id","purchase_order_lines.csv":"po_line_id","deliveries.csv":"delivery_id",
 "workflow_events.csv":"event_id"}
FKS = [("budgets.csv","department_id","departments.csv","department_id"),("requesters.csv","department_id","departments.csv","department_id"),
 ("purchase_requests.csv","requester_id","requesters.csv","requester_id"),("purchase_requests.csv","department_id","departments.csv","department_id"),
 ("purchase_requests.csv","budget_id","budgets.csv","budget_id"),("request_lines.csv","request_id","purchase_requests.csv","request_id"),
 ("rfqs.csv","request_id","purchase_requests.csv","request_id"),("supplier_quotes.csv","rfq_id","rfqs.csv","rfq_id"),
 ("supplier_quotes.csv","supplier_id","suppliers.csv","supplier_id"),("approvals.csv","request_id","purchase_requests.csv","request_id"),
 ("purchase_orders.csv","request_id","purchase_requests.csv","request_id"),("purchase_orders.csv","rfq_id","rfqs.csv","rfq_id"),
 ("purchase_orders.csv","quote_id","supplier_quotes.csv","quote_id"),("purchase_orders.csv","supplier_id","suppliers.csv","supplier_id"),
 ("purchase_order_lines.csv","po_id","purchase_orders.csv","po_id"),("purchase_order_lines.csv","request_line_id","request_lines.csv","request_line_id"),
 ("deliveries.csv","po_id","purchase_orders.csv","po_id"),("awarded_quotes.csv","po_id","purchase_orders.csv","po_id"),
 ("awarded_quotes.csv","quote_id","supplier_quotes.csv","quote_id"),("awarded_quotes.csv","supplier_id","suppliers.csv","supplier_id")]

def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as f: return list(csv.DictReader(f))
def num(value): return float(value)
def validate(data_dir="data/generated"):
    root=Path(data_dir); errors=[]; warnings=[]; tables={}
    for fn, cols in REQUIRED.items():
        path=root/fn
        if not path.exists(): errors.append(f"Missing file: {fn}"); continue
        rows=read_csv(path); tables[fn]=rows
        if rows:
            for col in cols:
                if col not in rows[0]: errors.append(f"{fn}: missing column {col}")
        elif fn not in ("approvals.csv",): errors.append(f"{fn}: unexpectedly empty")
    if (root/"workflow_events.csv").exists(): tables["workflow_events.csv"]=read_csv(root/"workflow_events.csv")
    for fn, pk in PK.items():
        if fn not in tables: continue
        vals=[r.get(pk,"") for r in tables[fn]]
        if any(not x for x in vals): errors.append(f"{fn}: blank {pk}")
        if len(vals)!=len(set(vals)): errors.append(f"{fn}: duplicate {pk}")
    for child,fk,parent,ppk in FKS:
        if child not in tables or parent not in tables: continue
        valid={r.get(ppk) for r in tables[parent]}
        for rowno,row in enumerate(tables[child],2):
            if row.get(fk) not in valid:
                errors.append(f"{child}:{rowno}: invalid {fk}={row.get(fk)}")
                if len(errors)>200: break
    for fn, a, b in [("purchase_requests.csv","created_date","needed_by_date"),("rfqs.csv","issued_date","due_date"),
                      ("supplier_quotes.csv","received_date","expiry_date")]:
        for rowno,row in enumerate(tables.get(fn,[]),2):
            try:
                if date.fromisoformat(row[a])>date.fromisoformat(row[b]): errors.append(f"{fn}:{rowno}: {a} after {b}")
            except (ValueError,KeyError,TypeError): errors.append(f"{fn}:{rowno}: invalid date")
    requests={r["request_id"]:r for r in tables.get("purchase_requests.csv",[])}
    quotes={r["quote_id"]:r for r in tables.get("supplier_quotes.csv",[])}
    suppliers={r["supplier_id"]:r for r in tables.get("suppliers.csv",[])}
    budgets={r["budget_id"]:r for r in tables.get("budgets.csv",[])}
    approvals=tables.get("approvals.csv",[])
    po_by_id={r["po_id"]:r for r in tables.get("purchase_orders.csv",[])}
    rfq_quotes={}
    for q in tables.get("supplier_quotes.csv",[]): rfq_quotes.setdefault(q["rfq_id"],[]).append(q)
    # Amount reconciliation and PO/quote identity.
    for po in tables.get("purchase_orders.csv",[]):
        try:
            calc=round(num(po["subtotal"])+num(po["shipping"])+num(po["tax"]),2)
            if abs(calc-num(po["total"]))>.01: errors.append(f"{po['po_id']}: total arithmetic mismatch")
            q=quotes.get(po["quote_id"])
            if q:
                if q["supplier_id"]!=po["supplier_id"]: errors.append(f"{po['po_id']}: PO supplier differs from selected quote")
                if q["currency"]!=po["currency"]: errors.append(f"{po['po_id']}: PO currency differs from selected quote")
                qtotal=round(num(q["subtotal"])+num(q["shipping"])+num(q["tax"]),2)
                if abs(qtotal-num(po["total"]))>.01: errors.append(f"{po['po_id']}: PO total differs from selected quote total")
                if date.fromisoformat(po["po_date"])>date.fromisoformat(q["expiry_date"]): warnings.append(f"{po['po_id']}: award after quote expiry (labelled anomaly expected for one fixture)")
            req=requests.get(po["request_id"])
            if req:
                budget=budgets.get(req["budget_id"])
                if budget and num(po["total"])>num(budget["allocated_amount"]): warnings.append(f"{po['po_id']}: exceeds linked budget allocation")
                if req["currency"]!=po["currency"]: warnings.append(f"{po['po_id']}: PO currency differs from request currency")
        except (ValueError,KeyError,TypeError): errors.append(f"{po.get('po_id','PO')}: invalid amount/date")
    # Baseline competitive RFQs need at least 3 quotes; this generated fixture uses competitive=true.
    for rfq in tables.get("rfqs.csv",[]):
        if rfq.get("competitive","").lower()=="true" and len(rfq_quotes.get(rfq["rfq_id"],[]))<3:
            errors.append(f"{rfq['rfq_id']}: competitive RFQ has fewer than 3 quotes")
    # Check labelled anomalies against the records they describe.
    truth={r["anomaly_id"]:r for r in tables.get("ground_truth.csv",[])}
    anomaly_results={}
    for anomaly_id, label in [("ANOM-01","PO-2026-000001"),("ANOM-02","PO-2026-000002"),("ANOM-03","PO-2026-000003"),
                              ("ANOM-04","PO-2026-000004"),("ANOM-05","PO-2026-000005"),("ANOM-07","PO-2026-000007")]:
        po=po_by_id.get(label); issues=[]
        if not po: issues.append("target PO missing")
        else:
            req=requests.get(po["request_id"]); q=quotes.get(po["quote_id"])
            if anomaly_id=="ANOM-01" and any(a["request_id"]==po["request_id"] and a["decision"].lower()=="approved" for a in approvals): issues.append("approved record exists")
            if anomaly_id=="ANOM-02" and q and date.fromisoformat(po["po_date"])<=date.fromisoformat(q["expiry_date"]): issues.append("quote does not expire before award")
            if anomaly_id=="ANOM-03" and q:
                peers=rfq_quotes.get(po["rfq_id"],[])
                selected_total=num(q["subtotal"])+num(q["shipping"])+num(q["tax"])
                peer_totals=[num(x["subtotal"])+num(x["shipping"])+num(x["tax"]) for x in peers if x["quote_id"]!=q["quote_id"] and x["currency"]==q["currency"]]
                if not peer_totals or selected_total<=min(peer_totals): issues.append("selected quote is not more expensive than eligible alternatives")
                if po.get("selection_rationale","").strip(): issues.append("selection rationale is not blank")
            if anomaly_id=="ANOM-04" and suppliers.get(po["supplier_id"],{}).get("active","").lower()!="false": issues.append("selected supplier is not inactive")
            if anomaly_id=="ANOM-05" and req:
                budget=budgets.get(req["budget_id"])
                if not budget or num(po["total"])<=num(budget["allocated_amount"]): issues.append("PO does not exceed linked budget")
            if anomaly_id=="ANOM-07" and q and req and q["currency"]==req["currency"]: issues.append("quote currency matches request currency")
        anomaly_results[anomaly_id]={"valid":not issues,"issues":issues}
        for issue in issues: errors.append(f"{anomaly_id}: {issue}")
    # Additional relationship, lifecycle and reconciliation checks.
    line_by_id = {r.get("request_line_id"): r for r in tables.get("request_lines.csv", [])}
    po_line_totals = {}
    po_line_quantities = {}
    for line in tables.get("purchase_order_lines.csv", []):
        po = po_by_id.get(line.get("po_id"))
        source_line = line_by_id.get(line.get("request_line_id"))
        if po and source_line and source_line.get("request_id") != po.get("request_id"):
            errors.append(f"{line.get('po_line_id')}: request line belongs to a different request than its PO")
        try:
            po_line_totals[line["po_id"]] = po_line_totals.get(line["po_id"], 0.0) + num(line["quantity_ordered"])*num(line["unit_price"])
            po_line_quantities[line["po_id"]] = po_line_quantities.get(line["po_id"], 0.0) + num(line["quantity_ordered"])
        except (ValueError, KeyError, TypeError):
            errors.append(f"{line.get('po_line_id','PO line')}: invalid quantity or unit price")
    for po in tables.get("purchase_orders.csv", []):
        q = quotes.get(po.get("quote_id"))
        if q and po.get("rfq_id") and q.get("rfq_id") != po.get("rfq_id"):
            errors.append(f"{po['po_id']}: selected quote belongs to a different RFQ")
        if po.get("po_id") in po_line_totals and abs(po_line_totals[po["po_id"]]-num(po["subtotal"])) > 0.02:
            errors.append(f"{po['po_id']}: PO line totals do not reconcile to PO subtotal")
    delivery_totals = {}
    for delivery in tables.get("deliveries.csv", []):
        try:
            delivery_totals[delivery["po_id"]] = delivery_totals.get(delivery["po_id"], 0.0) + num(delivery["quantity_received"])
            expected = num(delivery["quantity_expected"])
            if delivery_totals[delivery["po_id"]] > expected + 0.001:
                errors.append(f"{delivery['delivery_id']}: received quantity exceeds expected quantity")
        except (ValueError, KeyError, TypeError):
            errors.append(f"{delivery.get('delivery_id','Delivery')}: invalid quantity")
    for po in tables.get("purchase_orders.csv", []):
        ordered = po_line_quantities.get(po["po_id"], 0.0)
        received = delivery_totals.get(po["po_id"], 0.0)
        status = str(po.get("status", "")).lower()
        if status == "received" and ordered and received < ordered - 0.001:
            errors.append(f"{po['po_id']}: status received but delivered quantity is short")
        if status == "partially_received" and ordered and not (0 < received < ordered):
            errors.append(f"{po['po_id']}: partially_received status does not match delivery quantities")
    for event in tables.get("workflow_events.csv", []):
        try: date.fromisoformat(event["event_date"])
        except (ValueError, KeyError, TypeError): errors.append(f"{event.get('event_id','Event')}: invalid event_date")

    # Duplicate fixture should have a matching request line and a ground-truth label.
    duplicate_label=truth.get("ANOM-06",{}).get("entity_id")
    duplicate_issues=[]
    if duplicate_label:
        duplicate_req=requests.get(duplicate_label)
        if not duplicate_req:
            duplicate_issues.append("duplicate request missing")
        else:
            if not any(x["request_id"]==duplicate_label for x in tables.get("request_lines.csv",[])):
                duplicate_issues.append("duplicate request has no request line")
            def norm_purpose(v): return str(v).replace(" (duplicate anomaly)", "").strip().casefold()
            matches=[]
            for candidate in requests.values():
                if candidate["request_id"] == duplicate_label: continue
                fields=("requester_id","department_id","budget_id","created_date","needed_by_date","currency","estimated_total")
                if all(str(candidate.get(k,"")) == str(duplicate_req.get(k,"")) for k in fields) and norm_purpose(candidate.get("business_purpose","")) == norm_purpose(duplicate_req.get("business_purpose","")):
                    matches.append(candidate["request_id"])
            if not matches: duplicate_issues.append("duplicate does not match a source request on documented fields")
    else: duplicate_issues.append("ground-truth label missing")
    anomaly_results["ANOM-06"]={"valid":not duplicate_issues,"issues":duplicate_issues}
    for issue in duplicate_issues: errors.append(f"ANOM-06: {issue}")
    # Labels must point to the expected business record and label name.
    expected_labels={"ANOM-01":"po_without_approval","ANOM-02":"quote_expired_before_award","ANOM-03":"selected_quote_not_cheapest","ANOM-04":"inactive_supplier","ANOM-05":"budget_overrun","ANOM-06":"duplicate_request","ANOM-07":"quote_currency_mismatch"}
    for aid, expected in expected_labels.items():
        if aid not in truth: errors.append(f"{aid}: ground-truth label missing")
        elif truth[aid].get("label") != expected: errors.append(f"{aid}: unexpected ground-truth label {truth[aid].get('label')}")
    return {"valid":not errors,"errors":errors,"warnings":warnings,
            "row_counts":{k:len(v) for k,v in tables.items()},"anomaly_checks":anomaly_results}

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--data",default="data/generated"); args=parser.parse_args()
    result=validate(args.data); print(json.dumps(result,indent=2)); raise SystemExit(0 if result["valid"] else 1)
if __name__=="__main__": main()
