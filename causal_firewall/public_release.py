"""Build and verify a sanitized public release from a completed Study 0 run."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


PUBLIC_FIELDS = (
    "sequence",
    "replicate_id",
    "architecture",
    "arm",
    "cue",
    "choice",
    "discard_reward",
    "model",
    "temperature",
    "input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "total_tokens",
    "packet_hash",
    "model_visible_hash",
    "inference_payload_hash",
    "carrier_field",
    "carrier_present",
    "canary_present",
    "retry_id",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def build_public_release(source_run: str | Path, output_dir: str | Path) -> Path:
    source = Path(source_run)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    summary = json.loads((source / "summary.json").read_text(encoding="utf-8"))
    analysis = json.loads((source / "analysis.json").read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in (source / "outcomes.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    if not summary.get("technical_pass") or len(rows) != 288:
        raise RuntimeError("source_run_not_complete")

    outcomes_path = output / "study0_behavioral_smoke_v2_public.csv"
    with outcomes_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PUBLIC_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in PUBLIC_FIELDS})

    cell_path = output / "study0_cell_results.csv"
    cell_fields = (
        "architecture",
        "cue",
        "arm",
        "n",
        "discard",
        "discard_rate",
        "exact_95_ci_lower",
        "exact_95_ci_upper",
    )
    with cell_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=cell_fields)
        writer.writeheader()
        for row in analysis["cell_results"]:
            writer.writerow(
                {
                    **{field: row[field] for field in cell_fields[:6]},
                    "exact_95_ci_lower": row["exact_95_ci"][0],
                    "exact_95_ci_upper": row["exact_95_ci"][1],
                }
            )

    metadata = {
        "study_id": summary["study_id"],
        "run_id": summary["run_id"],
        "release_scope": "sanitized_developmental_study0_results",
        "model_snapshot": summary["model_snapshot"],
        "temperature": summary["temperature"],
        "planned_calls": summary["planned_calls"],
        "completed_calls": summary["completed_calls"],
        "total_input_tokens": summary["total_input_tokens"],
        "total_output_tokens": summary["total_output_tokens"],
        "total_tokens": summary["total_tokens"],
        "estimated_usd_at_recorded_rates": summary["estimated_usd"],
        "technical_pass": summary["technical_pass"],
        "gates": summary["gates"],
        "source_dry_run_id": summary["source_dry_run_id"],
        "source_temperature_gate_id": summary["source_temperature_gate_id"],
        "removed_private_fields": [
            "response_id",
            "authorization metadata",
            "local filesystem paths",
        ],
        "inference_boundary": (
            "Developmental API draws, not human participants and not a "
            "confirmatory sample."
        ),
    }
    metadata_path = output / "study0_run_metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    analysis_path = output / "study0_analysis.json"
    analysis_path.write_text(
        json.dumps(analysis, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    codebook = """# Study 0 public data codebook

`study0_behavioral_smoke_v2_public.csv` contains one row per API response draw.
The response identifier and local authorization record were removed. Hashes are
retained to verify request equivalence and information-flow invariance.

- `architecture`: A monolithic, B default handoff, C manual whitelist, or D labeled firewall.
- `arm`: human allocation or random allocation.
- `cue`: no research hypothesis, aligned hypothesis, or reversed hypothesis.
- `choice`: model output after strict schema validation.
- `discard_reward`: deterministic binary coding of `choice`.
- `model_visible_hash`: hash of instructions, input, and structured-output schema.
- `inference_payload_hash`: hash of every inference-relevant request field except API metadata.
- `carrier_present` and `canary_present`: whether the designated hidden-information carrier or canary reached the participant packet.
- `retry_id`: zero for every released row because content retries were prohibited.

`study0_cell_results.csv` contains cell counts, discard rates, and exact 95 percent
Clopper Pearson intervals. `study0_analysis.json` contains Delta and Gamma
estimands and the shared no-cue baseline.
"""
    (output / "README.md").write_text(codebook, encoding="utf-8")

    released = [outcomes_path, cell_path, metadata_path, analysis_path, output / "README.md"]
    manifest = {
        "files": {
            path.name: {"sha256": _sha256(path), "bytes": path.stat().st_size}
            for path in released
        }
    }
    manifest_path = output / "release_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return output


def verify_public_release(output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    manifest = json.loads((output / "release_manifest.json").read_text(encoding="utf-8"))
    hash_checks = {
        name: _sha256(output / name) == details["sha256"]
        for name, details in manifest["files"].items()
    }
    outcomes_path = output / "study0_behavioral_smoke_v2_public.csv"
    raw_text = outcomes_path.read_text(encoding="utf-8")
    with outcomes_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    forbidden_tokens = ("response_id", "authorization_source", "sk-" + "proj-")
    result = {
        "hashes_valid": all(hash_checks.values()),
        "hash_checks": hash_checks,
        "rows": len(rows),
        "rows_valid": len(rows) == 288,
        "forbidden_tokens_absent": all(token not in raw_text for token in forbidden_tokens),
    }
    result["passed"] = (
        result["hashes_valid"]
        and result["rows_valid"]
        and result["forbidden_tokens_absent"]
    )
    return result
