PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS departments (
  department_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  cost_center TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS budgets (
  budget_id TEXT PRIMARY KEY,
  department_id TEXT NOT NULL REFERENCES departments(department_id),
  fiscal_year INTEGER NOT NULL,
  currency TEXT NOT NULL CHECK(currency IN ('INR','USD','EUR','GBP')),
  allocated_amount REAL NOT NULL CHECK(allocated_amount >= 0),
  reserved_amount REAL NOT NULL DEFAULT 0 CHECK(reserved_amount >= 0),
  spent_amount REAL NOT NULL DEFAULT 0 CHECK(spent_amount >= 0),
  UNIQUE(department_id,fiscal_year,currency)
);
CREATE TABLE IF NOT EXISTS requesters (
  requester_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  department_id TEXT NOT NULL REFERENCES departments(department_id),
  active TEXT NOT NULL CHECK(lower(active) IN ('true','false','1','0','yes','no','active','inactive'))
);
CREATE TABLE IF NOT EXISTS suppliers (
  supplier_id TEXT PRIMARY KEY,
  supplier_code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  currency TEXT NOT NULL,
  active TEXT NOT NULL CHECK(lower(active) IN ('true','false','1','0','yes','no','active','inactive')),
  risk_flag TEXT NOT NULL,
  payment_terms_days INTEGER NOT NULL CHECK(payment_terms_days >= 0)
);
CREATE TABLE IF NOT EXISTS purchase_requests (
  request_id TEXT PRIMARY KEY,
  requester_id TEXT NOT NULL REFERENCES requesters(requester_id),
  department_id TEXT NOT NULL REFERENCES departments(department_id),
  budget_id TEXT NOT NULL REFERENCES budgets(budget_id),
  created_date TEXT NOT NULL,
  needed_by_date TEXT NOT NULL,
  currency TEXT NOT NULL,
  status TEXT NOT NULL,
  estimated_total REAL NOT NULL CHECK(estimated_total >= 0),
  business_purpose TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS request_lines (
  request_line_id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL REFERENCES purchase_requests(request_id),
  line_number INTEGER NOT NULL CHECK(line_number > 0),
  item_code TEXT,
  description TEXT NOT NULL,
  quantity REAL NOT NULL CHECK(quantity > 0),
  unit TEXT,
  estimated_unit_price REAL NOT NULL CHECK(estimated_unit_price >= 0),
  currency TEXT NOT NULL,
  UNIQUE(request_id,line_number)
);
CREATE TABLE IF NOT EXISTS rfqs (
  rfq_id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL REFERENCES purchase_requests(request_id),
  issued_date TEXT NOT NULL,
  due_date TEXT NOT NULL,
  status TEXT NOT NULL,
  competitive TEXT NOT NULL,
  currency TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS supplier_quotes (
  quote_id TEXT PRIMARY KEY,
  rfq_id TEXT NOT NULL REFERENCES rfqs(rfq_id),
  supplier_id TEXT NOT NULL REFERENCES suppliers(supplier_id),
  received_date TEXT NOT NULL,
  expiry_date TEXT NOT NULL,
  currency TEXT NOT NULL,
  subtotal REAL NOT NULL CHECK(subtotal >= 0),
  shipping REAL NOT NULL CHECK(shipping >= 0),
  tax REAL NOT NULL CHECK(tax >= 0),
  lead_time_days INTEGER NOT NULL CHECK(lead_time_days >= 0),
  status TEXT NOT NULL,
  UNIQUE(rfq_id,supplier_id,received_date)
);
CREATE TABLE IF NOT EXISTS approvals (
  approval_id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL REFERENCES purchase_requests(request_id),
  approver_id TEXT NOT NULL,
  decision TEXT NOT NULL CHECK(decision IN ('approved','rejected','pending','auto_approved')),
  decision_date TEXT NOT NULL,
  threshold_rule TEXT
);
CREATE TABLE IF NOT EXISTS purchase_orders (
  po_id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL REFERENCES purchase_requests(request_id),
  rfq_id TEXT REFERENCES rfqs(rfq_id),
  quote_id TEXT REFERENCES supplier_quotes(quote_id),
  supplier_id TEXT NOT NULL REFERENCES suppliers(supplier_id),
  po_date TEXT NOT NULL,
  currency TEXT NOT NULL,
  subtotal REAL NOT NULL CHECK(subtotal >= 0),
  shipping REAL NOT NULL CHECK(shipping >= 0),
  tax REAL NOT NULL CHECK(tax >= 0),
  total REAL NOT NULL CHECK(total >= 0),
  status TEXT NOT NULL,
  selection_rationale TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS awarded_quotes (
  po_id TEXT NOT NULL REFERENCES purchase_orders(po_id),
  quote_id TEXT NOT NULL REFERENCES supplier_quotes(quote_id),
  supplier_id TEXT NOT NULL REFERENCES suppliers(supplier_id),
  award_date TEXT NOT NULL,
  PRIMARY KEY(po_id,quote_id)
);
CREATE TABLE IF NOT EXISTS purchase_order_lines (
  po_line_id TEXT PRIMARY KEY,
  po_id TEXT NOT NULL REFERENCES purchase_orders(po_id),
  request_line_id TEXT NOT NULL REFERENCES request_lines(request_line_id),
  description TEXT NOT NULL,
  quantity_ordered REAL NOT NULL CHECK(quantity_ordered > 0),
  unit_price REAL NOT NULL CHECK(unit_price >= 0),
  currency TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deliveries (
  delivery_id TEXT PRIMARY KEY,
  po_id TEXT NOT NULL REFERENCES purchase_orders(po_id),
  event_date TEXT NOT NULL,
  event_type TEXT NOT NULL,
  quantity_received REAL NOT NULL CHECK(quantity_received >= 0),
  quantity_expected REAL NOT NULL CHECK(quantity_expected >= 0),
  notes TEXT
);
CREATE TABLE IF NOT EXISTS workflow_events (
  event_id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  event_date TEXT NOT NULL,
  actor_id TEXT,
  details TEXT
);
CREATE INDEX IF NOT EXISTS idx_requests_department ON purchase_requests(department_id);
CREATE INDEX IF NOT EXISTS idx_requests_status ON purchase_requests(status);
CREATE INDEX IF NOT EXISTS idx_quotes_rfq ON supplier_quotes(rfq_id);
CREATE INDEX IF NOT EXISTS idx_orders_supplier ON purchase_orders(supplier_id);
CREATE INDEX IF NOT EXISTS idx_events_entity ON workflow_events(entity_type,entity_id);
-- Evaluation metadata is deliberately stored separately in ground_truth.csv/json.
