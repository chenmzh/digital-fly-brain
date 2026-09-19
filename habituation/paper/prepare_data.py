#!/usr/bin/env python3
"""Create manuscript tables/plot data from audited results, using only stdlib.

Does not simulate, fit, or modify the experiment. Derived files can be regenerated.
"""
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean

HERE = Path(__file__).resolve().parent
ANALYSIS = HERE.parent / "analysis"
DATA = HERE / "data"


def load_csv(name):
    with (ANALYSIS / name).open(newline="") as f:
        return list(csv.DictReader(f))


def number(row, key):
    return float(row[key])


def write_csv(name, fields, rows):
    with (DATA / name).open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    DATA.mkdir(exist_ok=True)
    responses = load_csv("responses.csv")
    metrics = load_csv("metrics_by_seed.csv")
    report = json.loads((ANALYSIS / "report.json").read_text())
    assert len(responses) == 280 and len(metrics) == 20
    by_condition = defaultdict(list)
    for row in responses:
        by_condition[(row["model"], int(float(row["interval_ms"])))].append(row)
    assert set(by_condition) == {(m,t) for m in ("static","std") for t in (500,2000)}
    main_rows = []
    downstream_rows = []
    for model in ("static", "std"):
        for interval in (500, 2000):
            condition = by_condition[(model, interval)]
            summary = next(r for r in report["descriptive_results"] if r["model"]==model and r["interval_ms"]==interval)
            selected_metrics = [r for r in metrics if r["model"]==model and int(float(r["interval_ms"]))==interval]
            assert len(selected_metrics)==5
            for field in ("initial", "early_mean", "late_mean", "decrement_fraction", "probe_2000", "probe_10000"):
                actual = mean(number(r,field) for r in selected_metrics)
                assert math.isclose(actual, summary[field+"_mean"], abs_tol=1e-12)
            train = []
            for pulse in range(12):
                values = [number(r,"aBN1") for r in condition if r["phase"]=="train" and int(r["pulse"])==pulse]
                assert len(values)==5
                train.append(dict(trial=pulse+1, mean=mean(values), low=min(values), high=max(values)))
            write_csv(f"train_{model}_{interval}.csv", ["trial","mean","low","high"], train)
            stages = ["initial", "late_mean", "probe_2000", "probe_10000"]
            recovery = []
            for stage, key in enumerate(stages):
                values = [number(r,key) for r in selected_metrics]
                avg=mean(values)
                recovery.append(dict(stage=stage, mean=avg, minus=avg-min(values), plus=max(values)-avg))
            write_csv(f"recovery_{model}_{interval}.csv", ["stage","mean","minus","plus"], recovery)
            label = f"M{0 if model=='static' else 1} / {interval/1000:g} s"
            fields = [summary[k+"_mean"] for k in ("initial","early_mean","late_mean","decrement_fraction","probe_2000","probe_10000")]
            main_rows.append(label+" & "+" & ".join(f"{x*100 if i==3 else x:.2f}" for i,x in enumerate(fields))+r" \\")
            first = [r for r in condition if r["phase"]=="train" and int(r["pulse"])==0]
            late = [r for r in condition if r["phase"]=="train" and int(r["pulse"])>=9]
            numbers=[mean(number(r,cell) for r in rows) for cell in ("aDN1","aDN2") for rows in (first,late)]
            downstream_rows.append(label+" & "+" & ".join(f"{x:.2f}" for x in numbers)+r" \\")
    (DATA/"main_rows.tex").write_text("\n".join(main_rows)+"\n")
    (DATA/"downstream_rows.tex").write_text("\n".join(downstream_rows)+"\n")
    individual=[]
    for r in metrics:
        if r["model"]!="std": continue
        values = [number(r,k) for k in ("initial","early_mean","late_mean","decrement_fraction","probe_2000","probe_10000")]
        individual.append(f"{r['seed']} & {number(r,'interval_ms')/1000:g} & "+" & ".join(f"{x*100 if i==3 else x:.2f}" for i,x in enumerate(values))+r" \\")
    (DATA/"individual_rows.tex").write_text("\n".join(individual)+"\n")
    paired=[]
    for seed in (1701,1702,1703,1704,1705):
        record={"seed":seed}
        for interval in (500,2000):
            r=next(x for x in metrics if x['model']=='std' and int(x['seed'])==seed and number(x,'interval_ms')==interval)
            record[f"D{interval}"]=100*number(r,"decrement_fraction")
        paired.append(record)
    write_csv("paired_decrement.csv",["seed","D500","D2000"],paired)
    inputs=[]
    for seed in (1701,1702,1703,1704,1705):
        rows=[r for r in responses if int(r['seed'])==seed]
        injected={int(r['input_events']) for r in rows};actual={int(r['sensory_spikes']) for r in rows}
        assert len(injected)==len(actual)==1
        inputs.append(f"{seed} & {injected.pop():,} & {actual.pop():,}"+r" \\")
    (DATA/"input_rows.tex").write_text("\n".join(inputs)+"\n")
    sources=[ANALYSIS/x for x in ("responses.csv","metrics_by_seed.csv","report.json")]
    sources+=[HERE.parent/"protocols/main_v1.json",Path(__file__)]
    manifest={"scope":"Derived manuscript material only; no new simulations or fitted results.",
              "source_sha256":{str(p.relative_to(HERE.parent)):sha(p) for p in sources},
              "response_windows":len(responses),"sequences":len(metrics),
              "checks":"Every main-table value independently recalculated from per-seed metrics and checked against report.json.",
              "generated_sha256":{p.name:sha(p) for p in sorted(DATA.iterdir()) if p.is_file()}}
    (HERE/"data_manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n")
    print("Verified 280 responses / 20 sequences; manuscript tables and plot data generated.")


if __name__=="__main__":
    main()
