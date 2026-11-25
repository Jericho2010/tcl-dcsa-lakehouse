"""Unit tests running real datacontract-cli lint, changelog, and breaking checks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tcl_compiler.compile_dcsa import CONTRACTS_ODCS_DIR, PROJECT_ROOT, compile_all


def _datacontract_bin() -> str:
    candidate = Path(sys.executable).parent / "datacontract"
    return str(candidate) if candidate.exists() else "datacontract"


def test_all_five_odcs_contracts_pass_datacontract_lint() -> None:
    """All 5 generated ODCS v3 contracts pass real datacontract lint with 0 errors."""
    compile_all()
    contract_files = sorted(CONTRACTS_ODCS_DIR.glob("*.odcs.yaml"))
    assert len(contract_files) == 5

    cli = _datacontract_bin()
    for contract in contract_files:
        proc = subprocess.run([cli, "lint", str(contract)], capture_output=True, text=True)
        assert proc.returncode == 0, f"Lint failed for {contract}:\n{proc.stdout}\n{proc.stderr}"


def test_datacontract_changelog_and_breaking_catch_schema_breakage() -> None:
    """Breaking fixture dropping supply_air_temp_c and narrowing setpoint_temp_c fails check."""
    compile_all()
    cli = _datacontract_bin()
    baseline = CONTRACTS_ODCS_DIR / "reeferpulse_iot_telemetry.odcs.yaml"
    breaking = PROJECT_ROOT / "tests" / "fixtures" / "reeferpulse_iot_telemetry_breaking.odcs.yaml"
    assert breaking.is_file()

    changelog = subprocess.run(
        [cli, "changelog", str(baseline), str(breaking)],
        capture_output=True,
        text=True,
    )
    assert changelog.returncode == 0, changelog.stderr
    assert "supply_air_temp_c" in changelog.stdout
    assert "setpoint_temp_c" in changelog.stdout

    breaking_check = subprocess.run(
        [cli, "breaking", str(baseline), str(breaking)],
        capture_output=True,
        text=True,
    )
    assert breaking_check.returncode != 0
    assert "supply_air_temp_c" in breaking_check.stdout
