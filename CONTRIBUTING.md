# Contributing to Tasman Container Line (TCL) DCSA Lakehouse

Thank you for exploring this reference architecture! Because every downstream contract, validation rule, and semantic artifact is compiled **one-way from Git**, please follow the zero-drift authoring loop below.

---

## 1. Zero-Drift Authoring Workflow

### Changing a DCSA Domain Entity, Regex, Bound, or PII Tag
1. Edit the source LinkML profile under `models/linkml/dcsa/` — **never** hand-edit files inside `generated/` or `contracts/odcs/`.
2. Recompile all derived artifacts:
   ```bash
   uv run python -m tcl_compiler.compile_dcsa
   ```
3. Verify all 5 compiled ODCS contracts pass `datacontract lint` and breaking-change gates:
   ```bash
   ./run.sh
   ```
4. Commit both the LinkML source change and its deterministic compiled outputs together so CI's `git diff --exit-code generated contracts` passes.

### Adding or Updating a Governed Business KPI
1. Edit [`semantic/ossie/dcsa_ops.ossie.yaml`](semantic/ossie/dcsa_ops.ossie.yaml) (flat Ossie `0.3.0.dev0` format).
   - Keep dataset-scoped `metrics:` aligned with qualified model-scoped `metrics:` so both `ossie-databricks` and `ossie-microsoft` emit the new measure cleanly.
   - Keep complex Power BI-only evaluation-context DAX in [`semantic/powerbi_overrides/dax_specialist_measures.tmdl`](semantic/powerbi_overrides/dax_specialist_measures.tmdl) instead of polluting the vendor-neutral spec.
2. Recompile the semantic spine:
   ```bash
   uv run python -m tcl_compiler.compile_semantic
   ```
3. Confirm `uv run pytest -v` and `uv run ruff check .` pass cleanly.

---

## 2. Architecture &amp; Hygiene Standards

- **Pure Subject Schemas Only:** Never introduce `dev_`, `stage_`, or `prod_` schema prefixes — isolate environments at the Unity Catalog (`catalog`) boundary.
- **Archify Diagrams Only (Zero Mermaid):** All architecture, dataflow, and workflow diagrams live under `docs/diagrams/` as verified Archify v3.0 specs + standalone HTML + PNG previews. Keep `.archify/` scratch folders untracked.
- **Strict Secret &amp; PII Hygiene:** Never commit tokens, PATs, workspace URLs, warehouse IDs, real email addresses, or personal workstation paths. Automated hygiene tests in [`tests/test_bundle_and_cicd.py`](tests/test_bundle_and_cicd.py) enforce these rules on every PR.
- **Tooling Standard:** Use `uv` strictly (`uv sync`, `uv run ...`) — never global `pip install`.
