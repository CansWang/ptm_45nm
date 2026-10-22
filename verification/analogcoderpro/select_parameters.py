#!/usr/bin/env python3
"""Explicitly promote independently verified results to tracked replay inputs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    catalog = json.loads((HERE / "catalog.json").read_text())
    pending = []
    for circuit in catalog["circuits"]:
        bench = HERE / circuit["directory"]
        source_hash = hashlib.sha256((bench / "testbench.cir").read_bytes()).hexdigest()
        selected = {}
        for key in ("hp/nominal", "lp/nominal", "lp/common_1v"):
            path = bench / "results" / key / "metrics.json"
            record = json.loads(path.read_text())
            model_path = HERE.parents[1] / f"45nm_{record['model'].upper()}_ngspice.pm"
            if (record["status"] not in ("PASS", "LIMITED")
                    or record["source_sha256"] != source_hash
                    or record["upstream_revision"] != catalog["revision"]
                    or record["model_sha256"] != hashlib.sha256(model_path.read_bytes()).hexdigest()):
                raise ValueError(f"Result is not independently verified against current sources: {path}")
            for name, value in record["parameters"].items():
                spec = circuit["parameters"][name]
                if not spec["low"]*(1-1e-12) <= value <= spec["high"]*(1+1e-12):
                    raise ValueError(f"Selected parameter is outside bounds: {path}: {name}")
            selected[key] = {name: record[name] for name in
                ("parameters", "optimization", "supply_v", "source_sha256", "model_sha256", "upstream_revision")}
            selected[key]["selected_status"] = record["status"]
        pending.append((bench / "parameters.json", selected))
    for path, selected in pending:
        path.write_text(json.dumps(selected, indent=2, allow_nan=False)+"\n")
    print(f"Saved {len(pending)*3} verified parameter sets in {len(pending)} tracked input files.")


if __name__ == "__main__":
    main()
