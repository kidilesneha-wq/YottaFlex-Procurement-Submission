"""Transactional procurement workflow operations for the Streamlit demo."""
from __future__ import annotations
import sqlite3
from datetime import date, datetime
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "generated"
DB_PATH = ROOT / "data" / "workflow_app.db"
OPERATIONAL_TABLES = [
    "departments", "budgets", "requesters", "suppliers", "purchase_requests",
    "request_lines", "rfqs", "supplier_quotes", "approvals", "purchase_orders",
    "purchase_order_lines", "deliveries", "awarded_quotes", "workflow_events"
]

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con

def _log(con, entity_type, entity_id, event_type, actor, details):
    con.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_timestamp TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        actor_id TEXT NOT NULL,
        details TEXT NOT NULL
    )""")
    con.execute("INSERT INTO audit_log(event_timestamp,entity_type,entity_id,event_type,actor_id,details) VALUES(?,?,?,?,?,?)",
                (datetime.now().isoformat(timespec="seconds"), entity_type, str(entity_id), event_type, actor, details))
    if _table_exists(con, "workflow_events"):
        cols = _columns(con, "workflow_events")
        vals = {"event_id": _next_id(con, "workflow_events", "event_id", "EVT", 7),
                "event_timestamp": datetime.now().isoformat(timespec="seconds"),
                "event_date": date.today().isoformat(), "entity_type": entity_type,
                "entity_id": str(entity_id), "event_type": event_type, "actor_id": actor, "details": details}
        names = [k for k in vals if k in cols]
        con.execute(f"INSERT INTO workflow_events ({','.join(names)}) VALUES ({','.join('?' for _ in names)})", [vals[k] for k in names])

def _table_exists(con, table):
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None

def _columns(con, table):
    return {r[1] for r in con.execute(f'PRAGMA table_info("{table}")')}

def _next_id(con, table, column, prefix, width=6):
    max_n = 0
    if _table_exists(con, table) and column in _columns(con, table):
        for row in con.execute(f'SELECT "{column}" FROM "{table}"'):
            import re
            m = re.search(r'(\d+)$', str(row[0] or ""))
            if m: max_n = max(max_n, int(m.group(1)))
    return f"{prefix}-{max_n+1:0{width}d}"

def initialize_db(force=False):
    """Seed a constrained operational SQLite DB; ground truth is deliberately excluded."""
    if DB_PATH.exists() and not force:
        with connect() as con:
            if _table_exists(con, "purchase_requests") and con.execute("SELECT COUNT(*) FROM purchase_requests").fetchone()[0] > 0:
                con.execute("CREATE TABLE IF NOT EXISTS audit_log (audit_id INTEGER PRIMARY KEY AUTOINCREMENT,event_timestamp TEXT NOT NULL,entity_type TEXT NOT NULL,entity_id TEXT NOT NULL,event_type TEXT NOT NULL,actor_id TEXT NOT NULL,details TEXT NOT NULL)")
                return
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists(): DB_PATH.unlink()
    schema_path = ROOT / "schema.sql"
    seed_path = DATA_DIR / "seed_data.sql"
    if not schema_path.exists() or not seed_path.exists():
        raise FileNotFoundError("schema.sql or data/generated/seed_data.sql is missing; generate the data first.")
    with connect() as con:
        con.executescript(schema_path.read_text(encoding="utf-8"))
        con.executescript(seed_path.read_text(encoding="utf-8"))
        con.execute("CREATE TABLE IF NOT EXISTS audit_log (audit_id INTEGER PRIMARY KEY AUTOINCREMENT,event_timestamp TEXT NOT NULL,entity_type TEXT NOT NULL,entity_id TEXT NOT NULL,event_type TEXT NOT NULL,actor_id TEXT NOT NULL,details TEXT NOT NULL)")
        con.commit()

def frame(table, where="1=1", params=()):
    with connect() as con:
        if not _table_exists(con, table): return pd.DataFrame()
        return pd.read_sql_query(f'SELECT * FROM "{table}" WHERE {where}', con, params=params)

def create_request(requester_id, budget_id, description, quantity, unit_price, needed_by, purpose, actor="REQUESTER"):
    with connect() as con:
        requester = con.execute("SELECT * FROM requesters WHERE requester_id=?", (requester_id,)).fetchone()
        budget = con.execute("SELECT * FROM budgets WHERE budget_id=?", (budget_id,)).fetchone()
        if not requester or not budget: raise ValueError("Select a valid requester and budget.")
        if str(requester["department_id"]) != str(budget["department_id"]): raise ValueError("Requester and budget must belong to the same department.")
        total = round(float(quantity) * float(unit_price), 2)
        if quantity <= 0 or unit_price < 0: raise ValueError("Quantity must be positive and price cannot be negative.")
        available_budget = float(budget["allocated_amount"]) - float(budget["reserved_amount"]) - float(budget["spent_amount"])
        if total > available_budget:
            raise ValueError(f"Estimated request exceeds available budget ({available_budget:.2f} INR). Select a valid budget or reduce the request.")
        rid = _next_id(con, "purchase_requests", "request_id", "PR-2026", 6)
        today = date.today().isoformat()
        status = "pending_approval" if total > 10000 else "approved"
        con.execute("INSERT INTO purchase_requests(request_id,requester_id,department_id,budget_id,created_date,needed_by_date,currency,status,estimated_total,business_purpose) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (rid, requester_id, requester["department_id"], budget_id, today, needed_by, "INR", status, total, purpose))
        line_number = con.execute("SELECT COUNT(*) FROM request_lines WHERE request_id=?", (rid,)).fetchone()[0] + 1
        line_id = f"PRL-{rid.rsplit('-', 1)[1]}-{line_number:02d}"
        con.execute("INSERT INTO request_lines(request_line_id,request_id,line_number,item_code,description,quantity,unit,estimated_unit_price,currency) VALUES(?,?,?,?,?,?,?,?,?)",
                    (line_id, rid, 1, "USER-ITEM", description, quantity, "each", unit_price, "INR"))
        if status == "approved":
            aid = _next_id(con, "approvals", "approval_id", "APR", 7)
            con.execute("INSERT INTO approvals(approval_id,request_id,approver_id,decision,decision_date,threshold_rule) VALUES(?,?,?,?,?,?)",
                        (aid, rid, "SYSTEM", "approved", today, "auto_approval_under_10000"))
        _log(con, "purchase_request", rid, "request_created", actor, f"Estimate INR {total:.2f}; status={status}")
        con.commit()
        return rid

def decide_approval(request_id, decision, approver_id, note=""):
    decision = decision.lower()
    if decision not in {"approved", "rejected"}: raise ValueError("Decision must be approved or rejected.")
    with connect() as con:
        req = con.execute("SELECT * FROM purchase_requests WHERE request_id=?", (request_id,)).fetchone()
        if not req: raise ValueError("Request not found.")
        if req["requester_id"] == approver_id: raise ValueError("Self-approval is not allowed.")
        if req["status"] not in {"pending", "pending_approval", "submitted"}: raise ValueError("Only pending requests can be decided.")
        aid = _next_id(con, "approvals", "approval_id", "APR", 7)
        today = date.today().isoformat()
        con.execute("INSERT INTO approvals(approval_id,request_id,approver_id,decision,decision_date,threshold_rule) VALUES(?,?,?,?,?,?)",
                    (aid, request_id, approver_id, decision, today, "manager_review_over_10000"))
        con.execute("UPDATE purchase_requests SET status=? WHERE request_id=?", (decision, request_id))
        _log(con, "purchase_request", request_id, f"approval_{decision}", approver_id, note or "Approval decision recorded")
        con.commit()

def create_rfq(request_id, due_date, actor="PROCESS_OWNER", competitive=None):
    with connect() as con:
        req = con.execute("SELECT * FROM purchase_requests WHERE request_id=?", (request_id,)).fetchone()
        if not req: raise ValueError("Request not found.")
        if req["status"] != "approved": raise ValueError("Only approved requests can be sourced.")
        if con.execute("SELECT 1 FROM rfqs WHERE request_id=?", (request_id,)).fetchone(): raise ValueError("An RFQ already exists for this request.")
        is_comp = float(req["estimated_total"]) > 25000 if competitive is None else bool(competitive)
        rfqid = _next_id(con, "rfqs", "rfq_id", "RFQ-2026", 6)
        today = date.today().isoformat()
        con.execute("INSERT INTO rfqs(rfq_id,request_id,issued_date,due_date,status,competitive,currency) VALUES(?,?,?,?,?,?,?)",
                    (rfqid, request_id, today, due_date, "open", "true" if is_comp else "false", req["currency"]))
        _log(con, "rfq", rfqid, "rfq_created", actor, f"Request {request_id}; competitive={is_comp}")
        con.commit(); return rfqid

def add_quote(rfq_id, supplier_id, expiry_date, subtotal, shipping, tax, lead_time_days, currency="INR", actor="PROCESS_OWNER"):
    with connect() as con:
        rfq = con.execute("SELECT * FROM rfqs WHERE rfq_id=?", (rfq_id,)).fetchone()
        supplier = con.execute("SELECT * FROM suppliers WHERE supplier_id=?", (supplier_id,)).fetchone()
        if not rfq or not supplier: raise ValueError("Select a valid RFQ and supplier.")
        if str(supplier["active"]).lower() not in {"true", "1", "yes", "active"}: raise ValueError("Inactive suppliers cannot submit quotes.")
        if float(subtotal) < 0 or float(shipping) < 0 or float(tax) < 0 or int(lead_time_days) < 0: raise ValueError("Quote values cannot be negative.")
        qid = _next_id(con, "supplier_quotes", "quote_id", f"QUO-{supplier['supplier_code']}-2026", 6)
        today = date.today().isoformat()
        con.execute("INSERT INTO supplier_quotes(quote_id,rfq_id,supplier_id,received_date,expiry_date,currency,subtotal,shipping,tax,lead_time_days,status) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (qid, rfq_id, supplier_id, today, expiry_date, currency, subtotal, shipping, tax, lead_time_days, "submitted"))
        _log(con, "supplier_quote", qid, "quote_received", actor, f"Landed cost={float(subtotal)+float(shipping)+float(tax):.2f} {currency}")
        con.commit(); return qid

def award_quote(rfq_id, quote_id, actor="PROCESS_OWNER", rationale="Lowest valid landed cost; delivery time used as tie-breaker"):
    with connect() as con:
        rfq = con.execute("SELECT * FROM rfqs WHERE rfq_id=?", (rfq_id,)).fetchone()
        quote = con.execute("SELECT * FROM supplier_quotes WHERE quote_id=? AND rfq_id=?", (quote_id, rfq_id)).fetchone()
        if not rfq or not quote: raise ValueError("RFQ or quote not found.")
        req = con.execute("SELECT * FROM purchase_requests WHERE request_id=?", (rfq["request_id"],)).fetchone()
        if req["status"] != "approved": raise ValueError("Request must be approved before award.")
        supplier = con.execute("SELECT * FROM suppliers WHERE supplier_id=?", (quote["supplier_id"],)).fetchone()
        if not supplier or str(supplier["active"]).lower() not in {"true", "1", "yes", "active"}: raise ValueError("Cannot award an inactive supplier.")
        if date.fromisoformat(quote["expiry_date"]) < date.today(): raise ValueError("Cannot award an expired quote.")
        if quote["currency"] != req["currency"]: raise ValueError("Quote currency must match request currency.")
        peers = con.execute("SELECT * FROM supplier_quotes WHERE rfq_id=? AND status IN ('submitted','valid') AND expiry_date>=? AND currency=?", (rfq_id, date.today().isoformat(), req["currency"])).fetchall()
        if str(rfq["competitive"]).lower() in {"true", "1", "yes"} and len(peers) < 3: raise ValueError("Competitive RFQ requires at least three currently valid quotes.")
        def cost(q): return float(q["subtotal"])+float(q["shipping"])+float(q["tax"])
        best = min(peers, key=lambda q: (cost(q), int(q["lead_time_days"]))) if peers else quote
        if quote_id != best["quote_id"] and not rationale.strip(): raise ValueError("A non-cheapest award requires a documented rationale.")
        if quote_id != best["quote_id"]: raise ValueError("For this demo, select the lowest landed-cost valid quote; non-cheapest awards require a separately reviewed exception.")
        total = round(cost(quote), 2)
        budget = con.execute("SELECT * FROM budgets WHERE budget_id=?", (req["budget_id"],)).fetchone()
        available = float(budget["allocated_amount"])-float(budget["reserved_amount"])-float(budget["spent_amount"])
        if total > available: raise ValueError(f"Budget exceeded: available {available:.2f}, quote total {total:.2f}.")
        poid = _next_id(con, "purchase_orders", "po_id", "PO-2026", 6)
        today = date.today().isoformat()
        con.execute("INSERT INTO purchase_orders(po_id,request_id,rfq_id,quote_id,supplier_id,po_date,currency,subtotal,shipping,tax,total,status,selection_rationale) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (poid, req["request_id"], rfq_id, quote_id, quote["supplier_id"], today, quote["currency"], quote["subtotal"], quote["shipping"], quote["tax"], total, "issued", rationale))
        con.execute("INSERT INTO awarded_quotes(po_id,quote_id,supplier_id,award_date) VALUES(?,?,?,?)", (poid, quote_id, quote["supplier_id"], today))
        lines = con.execute("SELECT * FROM request_lines WHERE request_id=?", (req["request_id"],)).fetchall()
        for line_number, line in enumerate(lines, start=1):
            lineid = f"POL-{poid.rsplit('-', 1)[1]}-{line_number:02d}"
            con.execute("INSERT INTO purchase_order_lines(po_line_id,po_id,request_line_id,description,quantity_ordered,unit_price,currency) VALUES(?,?,?,?,?,?,?)",
                        (lineid, poid, line["request_line_id"], line["description"], line["quantity"], round(float(quote["subtotal"])/max(float(line["quantity"]),1),6), quote["currency"]))
        con.execute("UPDATE budgets SET reserved_amount=? WHERE budget_id=?", (float(budget["reserved_amount"])+total, req["budget_id"]))
        con.execute("UPDATE rfqs SET status='awarded' WHERE rfq_id=?", (rfq_id,))
        _log(con, "purchase_order", poid, "purchase_order_issued", actor, f"Quote {quote_id}; total={total:.2f}; rationale={rationale}")
        con.commit(); return poid

def record_delivery(po_id, quantity_received, event_type, notes="", actor="OPERATIONS"):
    with connect() as con:
        po = con.execute("SELECT * FROM purchase_orders WHERE po_id=?", (po_id,)).fetchone()
        if not po: raise ValueError("Purchase order not found.")
        if quantity_received < 0: raise ValueError("Received quantity cannot be negative.")
        expected = con.execute("SELECT COALESCE(SUM(quantity_ordered),0) FROM purchase_order_lines WHERE po_id=?", (po_id,)).fetchone()[0]
        received = con.execute("SELECT COALESCE(SUM(quantity_received),0) FROM deliveries WHERE po_id=?", (po_id,)).fetchone()[0]
        if received + quantity_received > expected: raise ValueError(f"Received quantity would exceed ordered quantity ({expected:g}).")
        did = f"DEL-{po_id}-{int(con.execute('SELECT COUNT(*) FROM deliveries WHERE po_id=?',(po_id,)).fetchone()[0])+1:02d}"
        today = date.today().isoformat()
        con.execute("INSERT INTO deliveries(delivery_id,po_id,event_date,event_type,quantity_received,quantity_expected,notes) VALUES(?,?,?,?,?,?,?)",
                    (did, po_id, today, event_type, quantity_received, expected, notes))
        new_received = received + quantity_received
        status = "received" if new_received >= expected else "partially_received"
        con.execute("UPDATE purchase_orders SET status=? WHERE po_id=?", (status, po_id))
        _log(con, "delivery", did, "delivery_recorded", actor, f"PO={po_id}; received={quantity_received}; cumulative={new_received}/{expected}; {notes}")
        con.commit(); return did

def exception_report():
    """Derive exceptions from operational records; does not read ground_truth labels."""
    pos = frame("purchase_orders")
    reqs = frame("purchase_requests").set_index("request_id", drop=False) if not frame("purchase_requests").empty else pd.DataFrame()
    quotes = frame("supplier_quotes").set_index("quote_id", drop=False) if not frame("supplier_quotes").empty else pd.DataFrame()
    suppliers = frame("suppliers").set_index("supplier_id", drop=False) if not frame("suppliers").empty else pd.DataFrame()
    budgets = frame("budgets").set_index("budget_id", drop=False) if not frame("budgets").empty else pd.DataFrame()
    approvals = frame("approvals")
    issues=[]
    for _, po in pos.iterrows():
        req=reqs.loc[po["request_id"]] if not reqs.empty and po["request_id"] in reqs.index else None
        q=quotes.loc[po["quote_id"]] if not quotes.empty and po["quote_id"] in quotes.index else None
        if req is not None and not ((approvals["request_id"].astype(str)==str(req["request_id"])) & (approvals["decision"].astype(str).str.lower()=="approved")).any():
            issues.append({"severity":"High","type":"PO without approval","entity_id":po["po_id"],"details":f"Request {req['request_id']} has no approved decision"})
        if q is not None and str(q["expiry_date"]) < str(po["po_date"]):
            issues.append({"severity":"High","type":"Expired quote awarded","entity_id":po["po_id"],"details":f"Quote expired {q['expiry_date']} before PO date {po['po_date']}"})
        if q is not None and str(po["selection_rationale"]).strip()=="":
            issues.append({"severity":"Medium","type":"Missing award rationale","entity_id":po["po_id"],"details":"Award rationale is blank"})
        if q is not None and str(po.get("rfq_id", "")):
            peer_quotes = frame("supplier_quotes", "rfq_id=?", (str(po["rfq_id"]),))
            if not peer_quotes.empty:
                eligible=[]
                for _, peer in peer_quotes.iterrows():
                    active = suppliers.loc[peer["supplier_id"], "active"] if peer["supplier_id"] in suppliers.index else "false"
                    valid = str(peer["expiry_date"]) >= str(po["po_date"]) and str(peer["currency"]) == str(q["currency"]) and str(active).lower() not in {"false","0","no","inactive"}
                    if valid:
                        eligible.append(float(peer["subtotal"])+float(peer["shipping"])+float(peer["tax"]))
                selected_cost=float(q["subtotal"])+float(q["shipping"])+float(q["tax"])
                if eligible and selected_cost > min(eligible)+0.01 and not str(po["selection_rationale"]).strip():
                    issues.append({"severity":"High","type":"Non-cheapest quote without rationale","entity_id":po["po_id"],"details":f"Selected landed cost {selected_cost:.2f} exceeds lowest valid cost {min(eligible):.2f} with no rationale"})
        if str(po["supplier_id"]) in suppliers.index and str(suppliers.loc[po["supplier_id"],"active"]).lower() in {"false","0","no","inactive"}:
            issues.append({"severity":"High","type":"Inactive supplier awarded","entity_id":po["po_id"],"details":f"Supplier {po['supplier_id']} is inactive"})
        if req is not None and str(req["budget_id"]) in budgets.index:
            b=budgets.loc[req["budget_id"]]
            if float(po["total"]) > float(b["allocated_amount"]): issues.append({"severity":"High","type":"Budget overrun","entity_id":po["po_id"],"details":f"PO total {float(po['total']):.2f} exceeds allocation {float(b['allocated_amount']):.2f}"})
        if q is not None and req is not None and str(q["currency"]) != str(req["currency"]):
            issues.append({"severity":"High","type":"Currency mismatch","entity_id":po["po_id"],"details":f"Quote {q['currency']} vs request {req['currency']}"})
    # Detect duplicate request candidates from business fields, not ground-truth labels.
    if not reqs.empty:
        def normalized_purpose(value):
            return str(value).replace(" (duplicate anomaly)", "").strip().casefold()
        records=reqs.to_dict("records")
        seen={}
        fields=("requester_id","department_id","budget_id","created_date","needed_by_date","currency","estimated_total")
        for record in records:
            signature=tuple(str(record.get(k,"")) for k in fields)+(normalized_purpose(record.get("business_purpose","")),)
            if signature in seen:
                issues.append({"severity":"Medium","type":"Duplicate request candidate","entity_id":record.get("request_id",""),"details":f"Matches request {seen[signature]} on requester, budget, dates, currency, estimate and purpose"})
            else:
                seen[signature]=record.get("request_id","")
    return pd.DataFrame(issues, columns=["severity","type","entity_id","details"])
