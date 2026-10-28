# Data model and relationships

## Core entities

- **Department 1:N Requester** — each requester belongs to one department.
- **Department 1:N Budget** — budgets are assigned to a department and fiscal year.
- **Requester 1:N PurchaseRequest** — a requester can submit multiple requests.
- **Department 1:N PurchaseRequest** and **Budget 1:N PurchaseRequest** — each request references one department and one budget.
- **PurchaseRequest 1:N RequestLine** — a request contains one or more requested items/services.
- **PurchaseRequest 1:N Approval** — approval decisions are recorded as separate records.
- **PurchaseRequest 0:N RFQ** — an approved request may be sourced through one or more RFQs.
- **RFQ N:M Supplier through SupplierQuote** — `SupplierQuote` is the associative/bridge entity and stores each supplier's commercial offer for an RFQ.
- **Supplier 1:N SupplierQuote** — a supplier can submit multiple quotes.
- **PurchaseRequest 0:N PurchaseOrder** — supports split awards or multiple orders where policy permits.
- **SupplierQuote 0:N PurchaseOrder** in the generated data — a quote can be referenced by multiple POs when the generator represents a split purchase; interactive award actions record each award explicitly.
- **PurchaseOrder 1:N PurchaseOrderLine** and **RequestLine 1:N PurchaseOrderLine** — PO lines trace back to requested lines.
- **PurchaseOrder 1:N Delivery** — delivery/receipt records preserve partial receipts and exception events.
- **WorkflowEvent 1:N entity history** — immutable event rows capture state transitions; `audit_log` stores interactive user actions.

## Lifecycle states

- Purchase request: `pending`, `pending_approval`, `approved`, `rejected`, `budget_review`.
- RFQ: `open`, `issued`, `awarded`, `closed`.
- Supplier quote: `submitted`, `valid`, `expired`, `rejected`.
- Purchase order: `issued`, `partially_received`, `received`, `closed`, `cancelled`.
- Delivery event: `partial_delivery`, `delivered`, `damaged_goods`, `delivery_delay`.

The app enforces core transitions for newly created records. Seeded anomaly fixtures intentionally violate selected rules for evaluation and must remain identifiable in validation output.

## ID conventions

- Request: `PR-2026-000001`
- RFQ: `RFQ-2026-000001`
- Quote: `QUO-S0001-2026-000001` (supplier-code segment)
- Purchase order: `PO-2026-000001`
- Delivery: `DEL-PO-2026-000001-01`

IDs are immutable and deterministic in the generated dataset. Interactive IDs increment from the largest existing suffix.

## Ground truth

Ground-truth metadata is maintained only in `data/generated/ground_truth.csv` and `ground_truth.json`. It is not a column in operational input features and is not imported into the application's operational database. Labels describe deliberately generated exception fixtures; the validator checks the actual operational facts independently.
