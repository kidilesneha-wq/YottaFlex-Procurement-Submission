# Validation report

Generated using seed `20261022` with the full-scale generator.

## Required row counts

| Dataset | Rows |
|---|---:|
| Requesters | 300 |
| Suppliers | 120 |
| Purchase requests | 1,201 (1,200 baseline + one labelled duplicate fixture) |
| RFQs | 500 |
| Supplier quotes | 1,500 |
| Purchase orders | 900 |
| Ground-truth labels | 7 |

## Automated validation

Run `python validate_data.py --data data/generated` to reproduce this check. The validator checks required files/columns, primary-key uniqueness, foreign-key joins, date ordering, PO amount reconciliation, supplier/quote consistency, competitive quote counts, duplicate request evidence, and the seven labelled anomaly fixtures.

The expected result is `valid: true` with zero errors. Warnings are intentionally reported for seeded exception records, including the expired quote, budget overrun, and currency mismatch. A warning is not silently treated as a normal operational outcome; it is a known fixture for evaluation.

The generator writes checksums for its generated CSV/JSON/SQL artifacts to `data/generated/manifest.json`. To demonstrate reproducibility, generate to two separate directories using the same seed and compare the manifest `sha256` maps.

## Ground truth isolation

`ground_truth.csv` and `ground_truth.json` are evaluation metadata. They are not included in `seed_data.sql`, are not imported into the operational app database, and are not used by the application's approval/award/exception logic. The validator reads them only to verify that the deliberately seeded anomaly fixtures match the declared labels.
