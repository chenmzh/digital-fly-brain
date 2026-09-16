#!/usr/bin/env python3
"""Small, serial FlyWire v630 experiments using the unmodified upstream model."""
import argparse
import ast
import gc
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time
from datetime import datetime, timezone

# Keep native libraries single-threaded; do not touch the user's global settings.
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[key] = "1"
os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True

import brian2 as b2
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "upstream" / "Drosophila_brain_model"
COMMIT = "91bdd1e7dcf193f3e7ca5a8933497fcef63b7960"
COMP = UPSTREAM / "2023_03_23_completeness_630_final.csv"
CON = UPSTREAM / "2023_03_23_connectivity_630_final.parquet"
sys.path.insert(0, str(UPSTREAM))
import model


def git(*args):
    return subprocess.check_output(["git", "-C", str(UPSTREAM), *args], text=True).strip()


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def notebook_inputs():
    """Read literal neuron IDs from the authors' notebook, never execute its cells."""
    wanted = {"neu_sugar", "neu_bitter", "id_mn9"}
    found = {}
    notebook = json.loads((UPSTREAM / "figures.ipynb").read_text())
    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        try:
            nodes = ast.parse("".join(cell["source"])).body
        except SyntaxError:
            continue
        for node in nodes:
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in wanted:
                    value = ast.literal_eval(node.value)
                    if target.id in found and found[target.id] != value:
                        raise ValueError(f"Conflicting notebook definitions: {target.id}")
                    found[target.id] = value
    if set(found) != wanted:
        raise ValueError("Missing notebook input definitions")
    if len(found["neu_sugar"]) != 21 or len(found["neu_bitter"]) != 21:
        raise ValueError("Unexpected input populations")
    return found


def audit_data(inputs):
    neurons = pd.read_csv(COMP, index_col=0)
    connections = pd.read_parquet(CON)
    ids = neurons.index.to_numpy()
    if len(ids) != 127400 or len(set(ids)) != len(ids):
        raise ValueError("Unexpected v630 neuron count or duplicate IDs")
    if len(connections) != 14687178 or connections.isna().any().any():
        raise ValueError("Unexpected connection table")
    for prefix in ("Presynaptic", "Postsynaptic"):
        ix = connections[f"{prefix}_Index"].to_numpy()
        if ix.min() < 0 or ix.max() >= len(ids):
            raise ValueError("Connection index out of bounds")
        if not np.array_equal(ids[ix], connections[f"{prefix}_ID"].to_numpy()):
            raise ValueError("Neuron IDs do not match connection indices")
    if not connections.Excitatory.isin([-1, 1]).all():
        raise ValueError("Unexpected synaptic sign")
    if not (connections.Connectivity > 0).all():
        raise ValueError("Nonpositive anatomical synapse count")
    if not np.array_equal(connections["Excitatory x Connectivity"],
                          connections.Excitatory * connections.Connectivity):
        raise ValueError("Signed connectivity mismatch")
    requested = inputs["neu_sugar"] + inputs["neu_bitter"] + [inputs["id_mn9"]]
    if not set(requested).issubset(set(ids)):
        raise ValueError("Unknown input/output neuron IDs")
    audit = {"neurons": len(ids), "directed_edges": len(connections),
             "anatomical_synapses": int(connections.Connectivity.sum()),
             "id_mapping_valid": True, "signed_weights_valid": True}
    return ids, audit


def upstream_reference(mn9):
    path = UPSTREAM / "results/example/sugarR_100Hz.parquet"
    df = pd.read_parquet(path)
    trials = sorted(int(t) for t in df.trial.unique())
    # The official example uses one-second trials; include zero-spike trials.
    rates = [int(((df.trial == t) & (df.flywire_id == mn9)).sum()) for t in trials]
    return {"file": str(path.relative_to(ROOT)), "sha256": sha256(path),
            "duration_seconds_from_official_example": 1.0, "trials": len(trials),
            "mn9_rates_hz": rates, "mn9_mean_hz": float(np.mean(rates)),
            "mn9_std_population_hz": float(np.std(rates)),
            "note": "Reference only; seeds are not supplied by the authors. No exact match required."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New directory; never overwritten")
    parser.add_argument("--duration-ms", type=float, default=1000)
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--seed", type=int, default=1701)
    parser.add_argument("--conditions", nargs="+", choices=["baseline", "sugar", "sugar_bitter"],
                        default=["baseline", "sugar", "sugar_bitter"])
    args = parser.parse_args()
    if not np.isfinite(args.duration_ms) or args.duration_ms <= 0 or args.trials < 1:
        parser.error("Duration must be finite/positive and trials >= 1")
    if args.seed < 0 or args.seed + args.trials > 2**32:
        parser.error("Seeds must be in NumPy's uint32 range")
    if len(set(args.conditions)) != len(args.conditions):
        parser.error("Duplicate conditions")
    if git("rev-parse", "HEAD") != COMMIT or git("status", "--porcelain"):
        raise RuntimeError("Upstream must match the pinned, clean commit")
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    metadata = {"status": "running", "created_utc": datetime.now(timezone.utc).isoformat(),
                "command": sys.argv, "upstream_commit": COMMIT,
                "python": sys.version, "platform": platform.platform(),
                "cpu": subprocess.check_output(["lscpu"], text=True),
                "memory_at_start": subprocess.check_output(["free", "-b"], text=True),
                "versions": {p: importlib.metadata.version(p) for p in
                             ["brian2", "numpy", "scipy", "pandas", "pyarrow", "Cython", "sympy", "joblib"]},
                "duration_ms": args.duration_ms, "trials_per_condition": args.trials,
                "seed_base": args.seed, "conditions": args.conditions,
                "dt_ms": 0.1, "codegen_target": "cython", "parallel_processes": 1,
                "upstream_default_params": {k: str(v) for k, v in model.default_params.items()},
                "effective_overrides": {"r_poi_hz": 100, "r_poi2_hz": 100,
                                        "t_run_ms": args.duration_ms, "n_run_per_call": 1},
                "protocol": "Sugar 100 Hz, bitter 100 Hz; full v630 graph, independent resets per trial.",
                "scope": "Small-sample qualitative replication, not all paper figures/164 predictions."}
    metadata["sha256"] = {str(p.relative_to(ROOT)): sha256(p) for p in
                          [COMP, CON, UPSTREAM / "model.py", UPSTREAM / "figures.ipynb",
                           Path(__file__).resolve(), ROOT / "requirements.txt"]}
    save_json(out / "manifest.json", metadata)
    (out / "runner_snapshot.py").write_bytes(Path(__file__).read_bytes())
    try:
        inputs = notebook_inputs()
        ids, audit = audit_data(inputs)
        metadata["data_audit"] = audit
        # JSON neuron identifiers are strings to avoid JavaScript's 53-bit limitation.
        save_json(out / "inputs.json", {k: [str(x) for x in v] if isinstance(v, list) else str(v)
                                         for k, v in inputs.items()})
        save_json(out / "reference.json", upstream_reference(inputs["id_mn9"]))
        save_json(out / "manifest.json", metadata)
        b2.prefs.codegen.target = "cython"  # Fail explicitly instead of silently using NumPy.
        rows = []
        id_to_index = {int(f): i for i, f in enumerate(ids)}
        index_to_id = dict(enumerate(ids))
        print("DATA", audit, flush=True)
        for condition in args.conditions:
            for trial in range(args.trials):
                gc.collect()
                b2.start_scope()
                b2.defaultclock.dt = 0.1 * b2.ms
                seed = args.seed + trial
                b2.seed(seed)
                params = dict(model.default_params)
                params.update(t_run=args.duration_ms * b2.ms, n_run=1,
                              r_poi=100 * b2.Hz, r_poi2=100 * b2.Hz)
                sugar = inputs["neu_sugar"] if condition != "baseline" else []
                bitter = inputs["neu_bitter"] if condition == "sugar_bitter" else []
                print(f"START {condition} trial={trial} seed={seed}", flush=True)
                t0 = time.perf_counter()
                spikes = model.run_trial(
                    exc=[id_to_index[n] for n in sugar],
                    exc2=[id_to_index[n] for n in bitter], slnc=[],
                    path_comp=COMP, path_con=CON, params=params)
                df = model.construct_dataframe([spikes], condition, index_to_id)
                df = df.astype({"t": "float64", "trial": "int64", "flywire_id": "int64"})
                df["trial"] = np.full(len(df), trial, dtype=np.int64)
                df["exp_name"] = pd.Series([condition] * len(df), dtype="string")
                seconds = args.duration_ms / 1000
                if not df.empty:
                    if not df.flywire_id.isin(ids).all() or not np.isfinite(df.t).all():
                        raise ValueError("Invalid spike IDs/times")
                    if df.t.min() < 0 or df.t.max() >= seconds:
                        raise ValueError("Spikes outside simulation interval")
                path = out / f"{condition}_trial{trial:02d}.parquet"
                df.to_parquet(path, index=False, compression="brotli")
                mn9_spikes = int((df.flywire_id == inputs["id_mn9"]).sum())
                row = {"condition": condition, "trial": trial, "seed": seed,
                       "duration_seconds": seconds, "spikes": len(df),
                       "active_neurons": int(df.flywire_id.nunique()),
                       "mn9_spikes": mn9_spikes, "mn9_hz": mn9_spikes / seconds,
                       "wall_seconds": time.perf_counter() - t0,
                       "process_peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
                       "spike_file": path.name, "sha256": sha256(path)}
                rows.append(row)
                pd.DataFrame(rows).to_csv(out / "trials.csv", index=False)
                print("DONE", json.dumps(row), flush=True)
                del spikes, df
        frame = pd.DataFrame(rows)
        grouped = frame.groupby("condition").mn9_hz
        summary = {"conditions": {c: {"mn9_mean_hz": float(v.mean()),
                                       "mn9_std_population_hz": float(v.std(ddof=0)),
                                       "trials": len(v)} for c, v in grouped},
                   "qualitative_checks": {}, "scope": metadata["scope"]}
        checks = summary["qualitative_checks"]
        if "baseline" in args.conditions:
            checks["baseline_has_no_spikes"] = bool((frame[frame.condition == "baseline"].spikes == 0).all())
        if args.duration_ms >= 1000 and "sugar" in args.conditions:
            checks["sugar_activates_mn9_all_trials"] = bool((frame[frame.condition == "sugar"].mn9_hz > 0).all())
            if "sugar_bitter" in args.conditions:
                checks["bitter_reduces_mean_mn9"] = bool(
                    grouped.mean()["sugar_bitter"] < grouped.mean()["sugar"])
        save_json(out / "summary.json", summary)
        if checks and not all(checks.values()):
            raise RuntimeError("Qualitative checks failed; inspect saved results")
        metadata["status"] = "completed"
    except BaseException as error:
        metadata["status"] = "failed"
        metadata["error"] = repr(error)
        raise
    finally:
        metadata["total_wall_seconds"] = time.perf_counter() - started
        metadata["process_peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        save_json(out / "manifest.json", metadata)
    print("RESULT", json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
