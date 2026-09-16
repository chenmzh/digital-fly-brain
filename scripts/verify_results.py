#!/usr/bin/env python3
"""Independently recalculate saved spike statistics and verify repeatability."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--repeat", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = args.run
    manifest = json.loads((out / "manifest.json").read_text())
    require(manifest["status"] == "completed", "Run did not complete")
    for name, expected in manifest["sha256"].items():
        require(digest(root / name) == expected, f"Changed input/source: {name}")
    require(digest(out / "runner_snapshot.py") == manifest["sha256"]["scripts/reproduce.py"],
            "Runner snapshot mismatch")
    inputs = json.loads((out / "inputs.json").read_text())
    mn9 = int(inputs["id_mn9"])
    ids = pd.read_csv(root / "upstream/Drosophila_brain_model/2023_03_23_completeness_630_final.csv",
                      index_col=0).index
    trials = pd.read_csv(out / "trials.csv")
    expected = {(c, t) for c in manifest["conditions"] for t in range(manifest["trials_per_condition"])}
    require(len(trials) == len(expected) and set(zip(trials.condition, trials.trial)) == expected,
            "Missing or duplicate trials")
    for row in trials.itertuples():
        path = out / row.spike_file
        require(digest(path) == row.sha256, f"Corrupt spike file: {path}")
        df = pd.read_parquet(path)
        require(df.flywire_id.dtype == np.dtype("int64"), "FlyWire IDs lost integer precision")
        require(df.flywire_id.isin(ids).all(), "Unknown neuron ID")
        require((df.trial == row.trial).all() and (df.exp_name == row.condition).all(), "Trial labels disagree")
        require(np.isfinite(df.t).all() and ((df.t >= 0) & (df.t < row.duration_seconds)).all(),
                "Invalid spike time")
        ticks = df.t.to_numpy() / (manifest["dt_ms"] / 1000)
        require(np.allclose(ticks, np.rint(ticks), atol=1e-8, rtol=0), "Off-grid spike times")
        require(not df.duplicated(["flywire_id", "t"]).any(), "Duplicate spikes")
        count = int((df.flywire_id == mn9).sum())
        require(count == row.mn9_spikes and count / row.duration_seconds == row.mn9_hz,
                "MN9 rate/count mismatch")
        require(len(df) == row.spikes and df.flywire_id.nunique() == row.active_neurons,
                "Global statistics mismatch")
        require(row.seed == manifest["seed_base"] + row.trial, "Seed metadata mismatch")
    summary = json.loads((out / "summary.json").read_text())
    for condition, sub in trials.groupby("condition"):
        expected_summary = summary["conditions"][condition]
        require(np.isclose(sub.mn9_hz.mean(), expected_summary["mn9_mean_hz"]), "Mean mismatch")
        require(np.isclose(sub.mn9_hz.std(ddof=0), expected_summary["mn9_std_population_hz"]), "SD mismatch")
    require((trials.loc[trials.condition == "baseline", "spikes"] == 0).all(), "Baseline is active")
    sugar = trials.loc[trials.condition == "sugar", "mn9_hz"]
    bitter = trials.loc[trials.condition == "sugar_bitter", "mn9_hz"]
    require(len(sugar) > 0 and (sugar > 0).all() and len(bitter) > 0 and bitter.mean() < sugar.mean(),
            "Missing or incorrect feeding/inhibition response")
    repeat_manifest = json.loads((args.repeat / "manifest.json").read_text())
    require(repeat_manifest["status"] == "completed", "Repeat failed")
    for key in ["upstream_commit", "duration_ms", "seed_base", "dt_ms", "codegen_target", "versions"]:
        require(repeat_manifest[key] == manifest[key], f"Repeat protocol mismatch: {key}")
    first = out / "sugar_trial00.parquet"
    repeated = args.repeat / "sugar_trial00.parquet"
    pd.testing.assert_frame_equal(pd.read_parquet(first), pd.read_parquet(repeated))
    result = {"status": "passed", "checked_trial_files": len(trials),
              "source_and_data_hashes_match": True, "spike_statistics_recomputed": True,
              "fixed_seed_repeat_identical": True,
              "repeat_file_sha256_equal": digest(first) == digest(repeated),
              "note": "Integrity and qualitative checks; not a statistical reproduction of all paper claims."}
    (out / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
