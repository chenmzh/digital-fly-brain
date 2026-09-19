#!/usr/bin/env python3
"""Continuous full-brain repeated-stimulus experiments; no parameter fitting."""
import argparse
import ast
import gc
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
from datetime import datetime, timezone

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[key] = "1"
os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
sys.dont_write_bytecode = True

import brian2 as b2
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
UP = ROOT / "upstream/Drosophila_brain_model"
COMMIT = "91bdd1e7dcf193f3e7ca5a8933497fcef63b7960"
COMP = UP / "2023_03_23_completeness_630_final.csv"
CON = UP / "2023_03_23_connectivity_630_final.parquet"
sys.path.insert(0, str(UP))
import model as upstream


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def inputs_from_notebook(name):
    found = []
    nb = json.loads((UP / "figures.ipynb").read_text())
    for cell in nb["cells"]:
        if cell["cell_type"] != "code":
            continue
        try:
            nodes = ast.parse("".join(cell["source"])).body
        except SyntaxError:
            continue
        for node in nodes:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                found.append(ast.literal_eval(node.value))
    require(found and all(x == found[0] for x in found), "Missing/conflicting input population")
    require(len(found[0]) == len(set(found[0])), "Duplicate input IDs")
    return found[0]


def validate_protocol(p):
    for key in ["dt_ms", "pulse_ms", "response_ms", "input_hz", "std_tau_ms"]:
        require(np.isfinite(p[key]) and p[key] > 0, f"Invalid {key}")
    require(p["response_ms"] >= p["pulse_ms"], "Response window shorter than stimulus")
    require(p["input_hz"] * p["dt_ms"] / 1000 < 1, "Bernoulli probability must be <1")
    require(0 <= p["std_U"] < 1, "Invalid depression fraction")
    require(p["n_pulses"] >= 3 and len(p["seeds"]) > 0, "Too few pulses/seeds")
    require(len(p["seeds"]) == len(set(p["seeds"])), "Duplicate seeds")
    require(set(p["models"]).issubset({"static", "std", "std_zero"}), "Unknown model")
    for t in [p["pulse_ms"], p["response_ms"], *p["onset_intervals_ms"], *p["recovery_ms"]]:
        require(np.isfinite(t) and t > 0 and np.isclose(t / p["dt_ms"], round(t / p["dt_ms"]), rtol=0, atol=1e-7), "Off-grid duration")
    require(min(p["onset_intervals_ms"]) >= p["response_ms"], "Overlapping response windows")


def input_pattern(seed, n, p):
    """A frozen realization of the upstream small-dt Poisson/Bernoulli drive."""
    bins = round(p["pulse_ms"] / p["dt_ms"])
    events = np.random.RandomState(seed).random_sample((n, bins)) < p["input_hz"] * p["dt_ms"] / 1000
    neuron, tick = np.nonzero(events)
    order = np.lexsort((neuron, tick))
    return neuron[order], tick[order]


class Brain:
    def __init__(self, p, variant, input_ids, neuron_ids):
        b2.start_scope()
        b2.defaultclock.dt = p["dt_ms"] * b2.ms
        b2.prefs.codegen.target = "cython"
        self.p = p
        self.ids = neuron_ids
        mapping = {int(x): i for i, x in enumerate(neuron_ids)}
        self.input_ix = np.array([mapping[x] for x in input_ids])
        self.read_ix = {k: mapping[int(v)] for k, v in p["readouts"].items()}
        self.neu, self.syn, self.monitor = upstream.create_model(COMP, CON, dict(upstream.default_params))
        require(len(self.neu) == 127400 and len(self.syn) == 14687178, "Wrong full-brain version")
        self.neu.rfc[self.input_ix] = 0 * b2.ms  # same as upstream.poi
        self.source = b2.SpikeGeneratorGroup(len(input_ids), [], [] * b2.ms, name="hab_source")
        self.inject = b2.Synapses(self.source, self.neu, on_pre="v_post += drive", name="hab_inject",
                                  namespace={"drive": upstream.default_params["w_syn"] * upstream.default_params["f_poi"]})
        self.inject.connect(i=np.arange(len(input_ids)), j=self.input_ix)
        objects = [self.neu, self.syn, self.monitor, self.source, self.inject]
        self.plastic = None
        self.replaced_edges = 0
        if variant != "static":
            pre = np.asarray(self.syn.i[:])
            candidates = np.flatnonzero(np.isin(pre, self.input_ix))
            weights = np.asarray(self.syn.w[candidates] / b2.mV)
            selected = candidates[weights > 0]
            self.replaced_edges = len(selected)
            require(self.replaced_edges > 0, "No excitatory afferent connections")
            j = np.asarray(self.syn.j[selected])
            weights = np.asarray(self.syn.w[selected] / b2.mV)
            self.plastic = b2.Synapses(
                self.neu, self.neu,
                model="w : volt\ndx/dt = (1-x)/tau_rec : 1 (event-driven)",
                on_pre="g_post += w*x\nx *= (1-U)",
                delay=upstream.default_params["t_dly"], name="hab_plastic",
                namespace={"tau_rec": p["std_tau_ms"] * b2.ms,
                           "U": p["std_U"] if variant == "std" else 0.0})
            self.plastic.connect(i=pre[selected], j=j)
            self.plastic.w = weights * b2.mV
            self.plastic.x = 1
            self.syn.w[selected] = 0 * b2.mV
            objects.append(self.plastic)
        self.net = b2.Network(*objects)
        self.net.store("initial")

    def resource_mean(self):
        if self.plastic is None:
            return 1.0
        elapsed = np.asarray((self.net.t - self.plastic.lastupdate[:]) / b2.ms)
        x = 1 - (1 - np.asarray(self.plastic.x[:])) * np.exp(-elapsed / self.p["std_tau_ms"])
        return float(x.mean())

    def pulse(self, pattern):
        p = self.p
        neuron, tick = pattern
        onset = float(self.net.t / b2.second)
        prior_count = np.asarray(self.monitor.count[:]).copy()
        start_event = int(self.monitor.num_spikes)
        state = {k: {"v_mV": float(self.neu.v[i] / b2.mV), "g_mV": float(self.neu.g[i] / b2.mV)}
                 for k, i in self.read_ix.items()}
        resource_before = self.resource_mean()
        self.source.set_spikes(neuron, self.net.t + tick * p["dt_ms"] * b2.ms, sorted=True)
        self.net.run(p["response_ms"] * b2.ms)
        counts = np.asarray(self.monitor.count[:]) - prior_count
        response = {"onset_s": onset, "input_events": len(neuron),
                    "sensory_spikes": int(counts[self.input_ix].sum()),
                    "total_spikes": int(counts.sum()), "resource_before": resource_before,
                    "resource_after": self.resource_mean()}
        event_i = np.asarray(self.monitor.i[start_event:])
        event_t = np.asarray(self.monitor.t[start_event:] / b2.second)
        for name, i in self.read_ix.items():
            response[name] = int(counts[i])
            matches = event_t[event_i == i]
            response[name + "_latency_ms"] = float((matches[0] - onset) * 1000) if len(matches) else None
            response[name + "_v_before_mV"] = state[name]["v_mV"]
            response[name + "_g_before_mV"] = state[name]["g_mV"]
        return response

    def save_spikes(self, path, start=0):
        ix = np.asarray(self.monitor.i[start:])
        frame = pd.DataFrame({"t_s": np.asarray(self.monitor.t[start:] / b2.second),
                              "flywire_id": self.ids[ix]})
        frame.to_parquet(path, index=False, compression="brotli")
        return {"file": path.name, "spikes": len(frame), "sha256": sha(path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=HERE / "protocols/main_v1.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()
    p = json.loads(args.protocol.read_text())
    if args.pilot:
        p.update(models=["static", "std_zero", "std"], seeds=p["seeds"][:1],
                 n_pulses=3, onset_intervals_ms=p["onset_intervals_ms"][:1], recovery_ms=[2000.0])
        p["id"] += "-pilot"
    validate_protocol(p)
    revision = subprocess.check_output(["git", "-C", str(UP), "rev-parse", "HEAD"], text=True).strip()
    require(revision == COMMIT, "Wrong upstream revision")
    require(not subprocess.check_output(["git", "-C", str(UP), "status", "--porcelain"], text=True).strip(), "Dirty upstream")
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out / "run_snapshot.py").write_bytes(Path(__file__).read_bytes())
    write_json(out / "protocol.json", p)
    ids = pd.read_csv(COMP, index_col=0).index.to_numpy(dtype=np.int64)
    input_ids = inputs_from_notebook(p["input_population"])
    require(set(input_ids + [int(v) for v in p["readouts"].values()]).issubset(set(ids)), "Unknown IDs")
    write_json(out / "neuron_ids.json", {"input": [str(i) for i in input_ids], "readouts": p["readouts"]})
    started = time.perf_counter()
    manifest = {"status": "running", "created_utc": datetime.now(timezone.utc).isoformat(),
                "upstream_commit": revision, "input_neurons": len(input_ids), "models": {},
                "python": sys.version,
                "versions": {x: importlib.metadata.version(x) for x in ["brian2", "numpy", "pandas", "pyarrow", "Cython"]},
                "sha256": {str(path.relative_to(ROOT)): sha(path) for path in
                           [COMP, CON, UP / "model.py", UP / "figures.ipynb", Path(__file__),
                            args.protocol.resolve(), HERE / "RESEARCH_PLAN.md"]},
                "files": [], "scope": "Conditional neural-output mechanism study; not proof of animal habituation."}
    write_json(out / "manifest.json", manifest)
    rows = []
    pilot_tables = {}
    try:
        for variant in p["models"]:
            gc.collect()
            print("BUILD", variant, flush=True)
            brain = Brain(p, variant, input_ids, ids)
            manifest["models"][variant] = {"neurons": len(brain.neu), "anatomical_edges": len(brain.syn),
                                          "replaced_excitatory_edges": brain.replaced_edges}
            for seed in p["seeds"]:
                pattern = input_pattern(seed, len(input_ids), p)
                pattern_path = out / f"pattern_seed{seed}.npz"
                if not pattern_path.exists():
                    np.savez_compressed(pattern_path, input_index=pattern[0], tick=pattern[1])
                    manifest["files"].append({"file": pattern_path.name, "sha256": sha(pattern_path)})
                for interval in p["onset_intervals_ms"]:
                    start = time.perf_counter()
                    brain.net.restore("initial", restore_random_state=True)
                    name = f"{variant}_s{seed}_T{int(interval)}"
                    local_rows = []
                    print("START", name, flush=True)
                    for pulse in range(p["n_pulses"]):
                        data = brain.pulse(pattern)
                        row = {"model": variant, "seed": seed, "interval_ms": interval,
                               "phase": "train", "pulse": pulse, "rest_ms": 0, **data}
                        rows.append(row)
                        local_rows.append(row)
                        if pulse < p["n_pulses"] - 1:
                            brain.net.run((interval - p["response_ms"]) * b2.ms)
                    trainfile = out / (name + "_train.parquet")
                    manifest["files"].append(brain.save_spikes(trainfile))
                    brain.net.store("trained")
                    trained_events = int(brain.monitor.num_spikes)
                    for rest in p["recovery_ms"]:
                        brain.net.restore("trained", restore_random_state=True)
                        brain.net.run(rest * b2.ms)
                        data = brain.pulse(pattern)
                        row = {"model": variant, "seed": seed, "interval_ms": interval,
                               "phase": "recovery", "pulse": -1, "rest_ms": rest, **data}
                        rows.append(row)
                        local_rows.append(row)
                        path = out / (name + f"_rest{int(rest)}.parquet")
                        manifest["files"].append(brain.save_spikes(path, trained_events))
                    # Pilot: replay the trained-state recovery branch, including its raw events.
                    if args.pilot:
                        original = pd.read_parquet(path)
                        brain.net.restore("trained", restore_random_state=True)
                        brain.net.run(rest * b2.ms)
                        brain.pulse(pattern)
                        replay_path = out / (name + "_restore_replay.parquet")
                        manifest["files"].append(brain.save_spikes(replay_path, trained_events))
                        pd.testing.assert_frame_equal(original, pd.read_parquet(replay_path))
                        pilot_tables[variant] = pd.read_parquet(trainfile)
                    pd.DataFrame(rows).to_csv(out / "responses.csv", index=False)
                    print("DONE", name, "primary", [r[p["primary_readout"]] for r in local_rows],
                          "seconds", round(time.perf_counter()-start, 2), flush=True)
                    manifest["elapsed_seconds"] = time.perf_counter() - started
                    write_json(out / "manifest.json", manifest)
            del brain
            gc.collect()
        if args.pilot:
            pd.testing.assert_frame_equal(pilot_tables["static"], pilot_tables["std_zero"])
            primary = p["primary_readout"]
            first = next(r for r in rows if r["model"] == "static" and r["phase"] == "train")
            require(first[primary] >= 5, "Pilot primary response below prespecified usability threshold (5 spikes)")
            manifest["pilot_checks"] = {"zero_U_matches_full_spikes": True, "restore_replay_matches": True,
                                         "primary_response_at_least_5_spikes": True}
        manifest["files"].append({"file": "responses.csv", "sha256": sha(out / "responses.csv")})
        manifest["files"].append({"file": "protocol.json", "sha256": sha(out / "protocol.json")})
        manifest["status"] = "completed"
    except BaseException as e:
        manifest["status"] = "failed"
        manifest["error"] = repr(e)
        raise
    finally:
        manifest["elapsed_seconds"] = time.perf_counter() - started
        manifest["process_peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        write_json(out / "manifest.json", manifest)
    print("FINISHED", manifest["status"], manifest["elapsed_seconds"], flush=True)


if __name__ == "__main__":
    main()
