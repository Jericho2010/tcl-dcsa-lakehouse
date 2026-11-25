# Power BI Specialist Overrides (`semantic/powerbi_overrides/`)

## Pattern: "Automate the Boring 80%, Protect the Specialist 20%"

This directory keeps complex Power BI DAX business logic decoupled from the core Apache Ossie specification ([`../ossie/dcsa_ops.ossie.yaml`](../ossie/dcsa_ops.ossie.yaml)):

1. **Automated 80% (`generated/powerbi/dcsa_ops.model.bim`)**
   - Compiled directly from `semantic/ossie/dcsa_ops.ossie.yaml` using real `ossie-microsoft export`.
   - Owns base tables, column bindings, star-schema relationships (`mv_container_journey_kpis.port_call_id -> mv_port_call_kpis.port_call_id`), AI context annotations, and the 10 portable KPI measures (`SUM`, `AVG`, `COUNT`, `COUNT(DISTINCT ...)`, and `DIVIDE(...)` ratios).
   - Never edited by hand — safe to regenerate on every CI build.

2. **Protected Specialist 20% (`dax_specialist_measures.tmdl`)**
   - Contains advanced Power BI-specific DAX patterns that depend on evaluation-context modifiers or iterator weighting (`CALCULATE`, `DATESINPERIOD`, `SUMX`) intentionally excluded from cross-platform Ossie SQL.
   - Kept in a separate override module so regenerating `dcsa_ops.model.bim` never overwrites executive time-intelligence or risk-weighted DAX measures.

## Note on `--pbip` Split-TMDL Export & .NET TOM

`apache-ossie-microsoft` emits TMSL (`dcsa_ops.model.bim`) natively in pure Python without proprietary dependencies. Passing `--pbip` additionally invokes .NET Tabular Object Model (`Microsoft.AnalysisServices` via `pythonnet` + `clr-loader` + restored NuGet DLLs). When TOM assemblies are absent in the local environment, `compile_semantic.py` cleanly records the `ossie-microsoft --pbip` probe diagnostic and relies on `dcsa_ops.model.bim` as the verified Power BI semantic artifact.
