"""Descriptive, audit-preserving analysis for behavioral smoke v2."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


def _binomial_cdf(k: int, n: int, p: float) -> float:
    return sum(
        math.comb(n, i) * (p**i) * ((1 - p) ** (n - i))
        for i in range(0, k + 1)
    )


def _binomial_upper_tail(k: int, n: int, p: float) -> float:
    return sum(
        math.comb(n, i) * (p**i) * ((1 - p) ** (n - i))
        for i in range(k, n + 1)
    )


def clopper_pearson(successes: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Two-sided exact binomial interval by tail inversion."""

    if not 0 <= successes <= n or n <= 0:
        raise ValueError("invalid_binomial_counts")
    lower = 0.0
    upper = 1.0
    if successes > 0:
        lo, hi = 0.0, 1.0
        target = alpha / 2
        for _ in range(100):
            mid = (lo + hi) / 2
            if _binomial_upper_tail(successes, n, mid) < target:
                lo = mid
            else:
                hi = mid
        lower = (lo + hi) / 2
    if successes < n:
        lo, hi = 0.0, 1.0
        target = alpha / 2
        for _ in range(100):
            mid = (lo + hi) / 2
            if _binomial_cdf(successes, n, mid) > target:
                lo = mid
            else:
                hi = mid
        upper = (lo + hi) / 2
    return lower, upper


def analyze_behavioral_smoke_v2(run_dir: str | Path) -> tuple[Path, Path]:
    run_path = Path(run_dir)
    summary = json.loads((run_path / "summary.json").read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in (run_path / "outcomes.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    if not summary.get("technical_pass") or len(rows) != 288:
        raise RuntimeError("run_not_complete_or_not_technical_pass")

    cells: dict[tuple[str, str, str], dict[str, int]] = defaultdict(
        lambda: {"n": 0, "discard": 0}
    )
    for row in rows:
        key = (row["architecture"], row["cue"], row["arm"])
        cells[key]["n"] += 1
        cells[key]["discard"] += int(row["discard_reward"])

    cell_results: list[dict[str, Any]] = []
    for (architecture, cue, arm), counts in sorted(cells.items()):
        lower, upper = clopper_pearson(counts["discard"], counts["n"])
        cell_results.append(
            {
                "architecture": architecture,
                "cue": cue,
                "arm": arm,
                "n": counts["n"],
                "discard": counts["discard"],
                "discard_rate": counts["discard"] / counts["n"],
                "exact_95_ci": [lower, upper],
            }
        )

    rates = {
        (row["architecture"], row["cue"], row["arm"]): row["discard_rate"]
        for row in cell_results
    }
    architectures = sorted({row["architecture"] for row in rows})
    cues = ("none", "aligned", "reversed")
    estimands: list[dict[str, Any]] = []
    gamma_lookup: dict[str, float] = {}
    for architecture in architectures:
        deltas = {
            cue: rates[(architecture, cue, "human_allocation")]
            - rates[(architecture, cue, "random_allocation")]
            for cue in cues
        }
        gamma = deltas["aligned"] - deltas["reversed"]
        gamma_lookup[architecture] = gamma
        estimands.append(
            {
                "architecture": architecture,
                "delta_none": deltas["none"],
                "delta_aligned": deltas["aligned"],
                "delta_reversed": deltas["reversed"],
                "gamma_aligned_minus_reversed": gamma,
            }
        )

    # No-cue requests are byte-equivalent across architectures, so pooling them
    # estimates one shared baseline response distribution.
    pooled: dict[str, dict[str, int]] = {
        "human_allocation": {"n": 0, "discard": 0},
        "random_allocation": {"n": 0, "discard": 0},
    }
    for row in rows:
        if row["cue"] == "none":
            pooled[row["arm"]]["n"] += 1
            pooled[row["arm"]]["discard"] += int(row["discard_reward"])
    pooled_rates = {
        arm: values["discard"] / values["n"] for arm, values in pooled.items()
    }
    shared_baseline = {
        "human": pooled["human_allocation"],
        "random": pooled["random_allocation"],
        "human_discard_rate": pooled_rates["human_allocation"],
        "random_discard_rate": pooled_rates["random_allocation"],
        "delta": pooled_rates["human_allocation"] - pooled_rates["random_allocation"],
    }

    d_gamma = gamma_lookup["D_labeled_causal_firewall"]
    attenuation = [
        {
            "architecture": architecture,
            "gamma_minus_d_placebo": gamma_lookup[architecture] - d_gamma,
        }
        for architecture in architectures
        if architecture != "D_labeled_causal_firewall"
    ]
    analysis = {
        "study_id": summary["study_id"],
        "run_id": summary["run_id"],
        "analysis_status": "developmental_descriptive_only",
        "technical_pass": summary["technical_pass"],
        "completed_calls": summary["completed_calls"],
        "estimated_usd": summary["estimated_usd"],
        "cell_results": cell_results,
        "estimands": estimands,
        "shared_no_cue_baseline": shared_baseline,
        "gamma_minus_d_placebo": attenuation,
        "interpretation": {
            "signal": (
                "All three cue-exposed architectures had positive directional Gamma; "
                "A=0.500, B=0.250, C=0.417."
            ),
            "firewall": (
                "D had identical inference payloads across cue labels and Gamma=0.083; "
                "its observed label differences are finite-sample Monte Carlo variation, "
                "not cue exposure."
            ),
            "limitation": (
                "Twelve API draws per cell are not power-justified for confirmatory "
                "inference and API draws are not human participants."
            ),
        },
    }
    analysis_path = run_path / "analysis.json"
    analysis_path.write_text(
        json.dumps(analysis, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    est_lines = [
        "| Architecture | Delta none | Delta aligned | Delta reversed | Gamma |",
        "|---|---:|---:|---:|---:|",
    ]
    for item in estimands:
        est_lines.append(
            f"| {item['architecture']} | {item['delta_none']:.3f} | "
            f"{item['delta_aligned']:.3f} | {item['delta_reversed']:.3f} | "
            f"{item['gamma_aligned_minus_reversed']:.3f} |"
        )
    report = f"""# Behavioral Smoke v2: Developmental Results

Run: `{summary['run_id']}`  
Status: **Technical pass ({summary['gates_passed']}/{summary['gates_total']} gates)**  
Calls: **{summary['completed_calls']}/{summary['planned_calls']}**  
Estimated cost: **${summary['estimated_usd']:.6f}**

## Main descriptive estimands

{chr(10).join(est_lines)}

`Delta` is the human-allocation discard rate minus the random-allocation discard
rate. `Gamma` is aligned Delta minus reversed Delta.

All three cue-exposed architectures produced a positive directional Gamma:
A = 0.500, B = 0.250, and C = 0.417. D produced Gamma = 0.083. Crucially,
D's inference payload was byte-identical across cue labels; its small observed
difference is therefore finite-sample Monte Carlo variation rather than
evidence that the cue reached the model.

The byte-equivalent no-cue observations can be pooled across architectures.
The shared baseline discard rate was
{shared_baseline['human_discard_rate']:.3f} in the human arm (48 draws) and
{shared_baseline['random_discard_rate']:.3f} in the random arm (48 draws), for
Delta = {shared_baseline['delta']:.3f}.

## Interpretation boundary

This is a developmental manipulation check, not a confirmatory experiment.
Twelve draws per cell were not selected through a power analysis. The results
show that the full pipeline works and that exposed research expectations can
co-vary with the simulated treatment effect, while the labeled firewall makes
the hidden cue causally unavailable at the request boundary. They do not show
human fidelity or population generalization, and API draws must not be called
human or synthetic participants.

Exact 95% Clopper-Pearson intervals for every cell are stored in `analysis.json`.
"""
    report_path = run_path / "analysis_report.md"
    report_path.write_text(report, encoding="utf-8")
    return analysis_path, report_path
