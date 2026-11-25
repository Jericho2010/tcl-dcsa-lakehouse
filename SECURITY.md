# Security & Data Governance Controls

## Reporting Issues
Report suspected vulnerabilities or credential exposures privately through a repository security advisory rather than opening public issues.

## Key Governance & Security Boundaries

1. **Zero Committed Secrets or Environment State**
   - `.env` and `.env.*` (except templates), `.venv/`, `.venvs/`, and `data/sample_landing/` are excluded via `.gitignore`.
   - Databricks hosts, SQL warehouse IDs, Kafka SASL credentials, and access tokens are read strictly at runtime from pipeline/app environment variables or CI/CD secrets (`DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `tcl.kafka.*`).

2. **PII Governance & 80/20 Dynamic Data Masking**
   - Sensitive DCSA eBL columns (`shipper_contact_email`, `consignee_name`) are annotated directly in [`models/linkml/dcsa/dcsa_ebl_v3.yaml`](models/linkml/dcsa/dcsa_ebl_v3.yaml) (`pii: "true"`, `classification: confidential`) and propagated automatically to [`generated/uc_comments.json`](generated/uc_comments.json) and ODCS contract [`contracts/odcs/voyagecore_ebl_bookings.odcs.yaml`](contracts/odcs/voyagecore_ebl_bookings.odcs.yaml).
   - [`src/jobs/deploy_serving_governance.py`](src/jobs/deploy_serving_governance.py) registers `<catalog>.governance_dcsa.mask_pii_email` and binds it to `shipper_contact_email` on curated Silver eBL tables (`silver_dcsa.silver_dcsa_ebl_current` and `silver_dcsa.silver_dcsa_ebl_history`, while dropping any legacy Bronze mask) so only `dcsa_pii_readers` sees unmasked email addresses.

3. **Zero-Drift Schema Quality & Quarantine**
   - Lakeflow Declarative Pipelines enforce LinkML-compiled rules (`dp.expect_all_or_drop`) across all Silver streaming tables and route violating rows (e.g., invalid ISO 6346 IDs, invalid UN/LOCODEs, `-99.0C` sensor faults) into dedicated Silver quarantine tables with per-rule violation reasons.
   - `src/jobs/run_contract_tests.py` verifies live UC tables against ODCS v3.1.0 contracts and records audit trails in `<catalog>.governance_dcsa.contract_test_results`.
