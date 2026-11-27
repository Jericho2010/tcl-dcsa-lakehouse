"""Unit tests validating DABs bundle configs, Genie Space, CI/CD YAML, and hygiene."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_databricks_bundle_structure_and_free_edition_constraints() -> None:
    """DABs bundle uses direct engine, pure schemas, 1 pipeline, 1 app, and 5-task job."""
    bundle = yaml.safe_load((PROJECT_ROOT / "databricks.yml").read_text(encoding="utf-8"))
    assert bundle["bundle"]["name"] == "tcl-dcsa-lakehouse"
    assert bundle["bundle"]["engine"] == "direct"
    assert bundle["variables"]["catalog"]["default"] == "workspace"
    assert set(bundle["targets"].keys()) == {"dev", "staging", "prod"}
    assert bundle["targets"]["dev"]["variables"]["catalog"] == "workspace"

    pipelines = yaml.safe_load(
        (PROJECT_ROOT / "resources" / "pipelines.yml").read_text(encoding="utf-8")
    )["resources"]["pipelines"]
    assert list(pipelines.keys()) == ["dcsa_medallion_pipeline"]
    pipe = pipelines["dcsa_medallion_pipeline"]
    assert pipe["serverless"] is True
    assert pipe["schema"] == "silver_dcsa"

    apps = yaml.safe_load(
        (PROJECT_ROOT / "resources" / "apps.yml").read_text(encoding="utf-8")
    )["resources"]["apps"]
    assert list(apps.keys()) == ["tcl_port_control"]
    assert apps["tcl_port_control"]["name"] == "tcl-port-control"

    jobs = yaml.safe_load(
        (PROJECT_ROOT / "resources" / "jobs.yml").read_text(encoding="utf-8")
    )["resources"]["jobs"]
    tasks = [t["task_key"] for t in jobs["tcl_dcsa_e2e_orchestrator"]["tasks"]]
    assert tasks == [
        "bootstrap_uc_objects",
        "ingest_harboursync_jit",
        "run_dcsa_medallion_pipeline",
        "deploy_serving_governance",
        "run_contract_tests",
    ]

    genies = yaml.safe_load(
        (PROJECT_ROOT / "resources" / "genie_spaces.yml").read_text(encoding="utf-8")
    )["resources"]["genie_spaces"]
    assert "tcl_ops_genie" in genies


def test_genie_space_and_cicd_workflows_parse_cleanly() -> None:
    """Genie Space JSON, GitHub Actions workflow, and Azure Pipelines YAML validate cleanly."""
    genie_path = PROJECT_ROOT / "src" / "genie" / "tcl_ops_genie.geniespace.json"
    genie = json.loads(genie_path.read_text(encoding="utf-8"))
    assert genie["version"] == 2
    mv_ids = {m["identifier"] for m in genie["data_sources"]["metric_views"]}
    assert mv_ids == {
        "workspace.gold_dcsa.mv_port_call_kpis",
        "workspace.gold_dcsa.mv_container_journey_kpis",
    }

    gh_ci = yaml.safe_load(
        (PROJECT_ROOT / ".github" / "workflows" / "ci-cd.yml").read_text(encoding="utf-8")
    )
    assert set(gh_ci["jobs"].keys()) == {"ci", "cd-databricks"}

    az_ci = yaml.safe_load((PROJECT_ROOT / "azure-pipelines.yml").read_text(encoding="utf-8"))
    stage_names = [s["stage"] for s in az_ci["stages"]]
    assert stage_names == ["Compile_And_Gate", "Deploy_Dev", "Deploy_Staging", "Deploy_Prod"]


def test_repository_contains_no_dev_prefixes_secrets_or_personal_paths() -> None:
    """Enforce zero prohibited prefixes, personal paths, emails, or tokens across repo."""
    # Construct regex strings dynamically so this test file contains zero literal pattern matches.
    forbidden_patterns = (
        re.compile(r"\b" + "dev" + r"_[a-z_]+"),
        re.compile(r"/" + "home/" + "shaun"),
        re.compile("gmail" + r"\." + "com", re.IGNORECASE),
        re.compile("dapi" + r"[0-9a-f]{20,}"),
        re.compile("github" + "_pat_" + "|" + "ghp" + "_"),
        re.compile("dbc-" + r"[a-z0-9-]+\.cloud\.databricks\.com", re.IGNORECASE),
        re.compile("databricksapps" + r"\." + "com", re.IGNORECASE),
        re.compile("shaun" + "david" + "anderson", re.IGNORECASE),
        re.compile("df4dc096" + "88caf6d8", re.IGNORECASE),
        re.compile("36714775" + "45521222"),
    )
    scan_roots = (
        "src",
        "apps",
        "resources",
        "models",
        "semantic",
        "contracts",
        "generated",
        "tests",
        "docs",
        ".github",
    )
    extra_files = (
        "databricks.yml",
        "azure-pipelines.yml",
        "setup.sh",
        "run.sh",
        "README.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        ".gitignore",
    )

    files: list[Path] = []
    for folder in scan_roots:
        files.extend(p for p in (PROJECT_ROOT / folder).rglob("*") if p.is_file())
    for fname in extra_files:
        files.append(PROJECT_ROOT / fname)

    for path in files:
        if path.suffix in {".pyc", ".png", ".jpg", ".webp"} or "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pat in forbidden_patterns:
            match = pat.search(text)
            assert match is None, (
                f"Forbidden pattern {pat.pattern!r} matched in {path}: {match.group(0)}"
            )


def test_documentation_uses_archify_diagrams_and_zero_mermaid() -> None:
    """Ensure all Archify showcase diagrams & infographics exist and zero Mermaid blocks remain."""
    expected_assets = (
        "docs/diagrams/tcl-platform-architecture.html",
        "docs/diagrams/tcl-platform-architecture.candidate.json",
        "docs/diagrams/images/tcl-platform-architecture.png",
        "docs/diagrams/tcl-medallion-dataflow.html",
        "docs/diagrams/tcl-medallion-dataflow.candidate.json",
        "docs/diagrams/images/tcl-medallion-dataflow.png",
        "docs/diagrams/tcl-cicd-orchestration.html",
        "docs/diagrams/tcl-cicd-orchestration.candidate.json",
        "docs/diagrams/images/tcl-cicd-orchestration.png",
        "docs/infographics/tcl_hero_banner.png",
        "docs/infographics/tcl_lakehouse_one_pager.png",
        "docs/infographics/tcl_80_20_blueprint.png",
        "docs/ARCHITECTURE.md",
        "docs/DCSA_DOMAIN_MODEL.md",
        "docs/DEPLOYMENT_GUIDE.md",
        "CONTRIBUTING.md",
    )
    for rel in expected_assets:
        assert (PROJECT_ROOT / rel).is_file(), f"Missing documentation asset: {rel}"

    md_files = [
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "CONTRIBUTING.md",
        PROJECT_ROOT / "SECURITY.md",
        *(PROJECT_ROOT / "docs").rglob("*.md"),
    ]
    mermaid_fence = re.compile(r"```" + r"\s*mermaid", re.IGNORECASE)
    for md in md_files:
        text = md.read_text(encoding="utf-8")
        assert mermaid_fence.search(text) is None, f"Mermaid block found in {md}"
