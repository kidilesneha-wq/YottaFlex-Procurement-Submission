# Submission checklist

- [ ] Extract the ZIP and install dependencies from `requirements.txt`.
- [ ] Run `python validate_data.py --data data/generated` and confirm `valid: true`.
- [ ] Run `python -m pytest -q` and confirm all tests pass.
- [ ] Run `python -m streamlit run app.py` and manually test request creation, approval, RFQ, quote capture/comparison, award, delivery, exceptions, and audit pages.
- [ ] Confirm `ground_truth.csv/json` are evaluation metadata only and are not in operational SQL seed or app tables.
- [ ] Create a **public** GitHub repository and push all required files.
- [ ] Open the public repository without signing in to confirm access.
- [ ] Submit the exact public repository URL before the deadline.
