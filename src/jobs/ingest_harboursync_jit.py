"""Serverless ingestion job landing HarbourSync JIT (and Free Edition DCSA feeds) to Volumes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _resolve_src_dir() -> str:
    start = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd().resolve()
    for candidate in (start, *start.parents):
        if (candidate / "src" / "generators").is_dir():
            return str(candidate / "src")
        if (candidate / "generators").is_dir():
            return str(candidate)
    return str(start)


_SRC_DIR = _resolve_src_dir()
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from generators.dcsa_synthetic_generator import generate_all  # noqa: E402


def run_ingestion(
    *,
    catalog: str | None = "workspace",
    ingestion_mode: str = "free_edition",
    output_dir: Path | None = None,
    seed: int = 42,
) -> dict[str, Path]:
    """Land DCSA operational JSONL payloads according to the deployment ingestion mode."""
    if ingestion_mode not in {"free_edition", "azure_enterprise"}:
        raise ValueError(f"Unsupported ingestion_mode: {ingestion_mode!r}")

    sources = (
        {"portgate_tos", "reeferpulse_iot", "voyagecore_cdc", "harboursync_jit"}
        if ingestion_mode == "free_edition"
        else {"portgate_tos", "harboursync_jit"}
    )
    target_catalog = None if output_dir is not None else catalog
    return generate_all(
        output_root=output_dir,
        catalog=target_catalog,
        seed=seed,
        sources=sources,
    )


def main(argv: list[str] | None = None) -> int:
    """Databricks serverless job entrypoint landing operational DCSA JSONL feeds."""
    parser = argparse.ArgumentParser(description="Land HarbourSync JIT & DCSA sources.")
    parser.add_argument("--catalog", default="workspace", help="Target UC catalog for Volumes.")
    parser.add_argument(
        "--ingestion-mode",
        choices=("free_edition", "azure_enterprise"),
        default="free_edition",
        help="Landing profile.",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=None, help="Optional local override dir."
    )
    parser.add_argument("--seed", type=int, default=42, help="Deterministic generator seed.")
    args = parser.parse_args(argv)

    written = run_ingestion(
        catalog=args.catalog,
        ingestion_mode=args.ingestion_mode,
        output_dir=args.output_dir,
        seed=args.seed,
    )
    for key, path in written.items():
        print(f"[ingest_harboursync_jit] {key}: {path}")
    return 0


if __name__ == "__main__":
    exit_code = main()
    if exit_code != 0:
        raise SystemExit(exit_code)
