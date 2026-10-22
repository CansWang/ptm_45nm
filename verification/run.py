#!/usr/bin/env python3
"""Run the PTM examples on HP/LP models, check waveforms, and save PNG plots."""

import argparse
import math
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from analogcoderpro import benchmark as acp


ROOT = Path(__file__).resolve().parent
BENCHES = {"inverter": "inv_vtc_tran.cir", "ring_oscillator": "ro11.cir"}
MODELS = {"hp": ("45nm_HP_ngspice.pm", 1.0), "lp": ("45nm_LP_ngspice.pm", 1.1)}
NGATE_WARNING = "Warning: Ngate = 1e+17 is less than 1.E18cm^-3."


def check(condition, message):
    if not condition:
        raise ValueError(message)


def load_waveform(path, header):
    lines = path.read_text().splitlines()
    check(bool(lines) and lines[0].split() == header, f"Invalid header in {path}")
    rows = [tuple(map(float, line.split())) for line in lines[1:] if line.strip()]
    check(bool(rows), f"No waveform data in {path}")
    check(all(len(row) == 3 and all(map(math.isfinite, row)) for row in rows),
          f"Invalid or nonfinite waveform data in {path}")
    check(all(b[0] > a[0] for a, b in zip(rows, rows[1:])),
          f"Waveform scale is not strictly increasing in {path}")
    return rows


def measurement(log, name):
    match = re.search(rf"^{name}\s*=\s*([\deE+.-]+)", log, re.MULTILINE)
    check(match is not None, f"Missing measurement: {name}")
    value = float(match.group(1))
    check(math.isfinite(value), f"Nonfinite measurement: {name}")
    return value


def crossings(rows, column, rising, threshold, after=0):
    times = []
    for a, b in zip(rows, rows[1:]):
        before, later = a[column] - threshold, b[column] - threshold
        crossed = before < 0 <= later if rising else before > 0 >= later
        if crossed:
            time = a[0] + (b[0] - a[0]) * (-before) / (later - before)
            if time >= after:
                times.append(time)
    return times


def check_duration(rows, stop):
    check(abs(rows[0][0]) < 1e-12 and abs(rows[-1][0] - stop) < 1e-18,
          f"Transient does not cover the expected 0 to {stop * 1e9:g} ns interval")


def validate_inverter(results, log, supply):
    dc = load_waveform(results / "vtc.dat", ["v-sweep", "v(in)", "v(out)"])
    tran = load_waveform(results / "tran.dat", ["time", "v(in)", "v(out)"])
    values = {name: measurement(log, name) for name in ("voh", "vol", "vm", "tphl", "tplh")}
    expected_rows = round(supply / 0.005) + 1
    check(len(dc) == expected_rows and all(abs(row[0] - i * 0.005) < 1e-10
          and abs(row[1] - row[0]) < 1e-10 for i, row in enumerate(dc)),
          "Incorrect DC sweep range or step")
    check(abs(dc[0][2] - supply) < 0.01 * supply and abs(dc[-1][2]) < 0.01 * supply,
          "DC output does not reach both rails")
    check(all(b[2] <= a[2] + 1e-9 for a, b in zip(dc, dc[1:])),
          "DC transfer curve is not monotonic")
    check(abs(values["voh"] - dc[0][2]) < 1e-7
          and abs(values["vol"] - dc[-1][2]) < 1e-7, "DC measurements disagree with data")
    check(0.35 * supply <= values["vm"] <= 0.65 * supply,
          "Inverter switching voltage is far from half-supply")
    check_duration(tran, 2e-9)
    # Sample well inside each half-cycle so slower LP transitions can settle.
    for start, stop, level in ((300e-12, 550e-12, 1), (850e-12, 1.05e-9, 0),
                               (1.3e-9, 1.55e-9, 1), (1.85e-9, 2e-9, 0)):
        samples = [row for row in tran if start <= row[0] <= stop]
        check(bool(samples) and all(abs(row[1] - level * supply) < 1e-9
              and abs(row[2] - (1 - level) * supply) < 0.01 * supply for row in samples),
              "Inverter input/output levels are incorrect during a settled half-cycle")
    for name, rising in (("tphl", False), ("tplh", True)):
        inputs = crossings(tran, 1, not rising, supply / 2)
        outputs = crossings(tran, 2, rising, supply / 2)
        check(len(inputs) == len(outputs) == 2, f"Incorrect edge count for {name}")
        delays = [out - inp for out, inp in zip(outputs, inputs)]
        check(all(0 < delay < 250e-12 for delay in delays),
              f"Propagation delay exceeds one quarter of the input period: {name}")
        check(abs(delays[0] - values[name]) < 1e-16, f"Waveform disagrees with {name}")
        check(abs(delays[1] - delays[0]) < 0.1e-12, f"Cycle-to-cycle delay changed: {name}")
    notes = [
        f"PASS: {expected_rows} finite DC rows; monotonic transfer curve and both output rails within 1%.",
        f"PASS: {len(tran)} finite transient rows; both input cycles invert correctly.",
        "PASS: independently interpolated delays match ngspice and repeat within 0.1 ps.",
    ]
    return values, dc, tran, notes


def validate_ring(results, log, supply):
    tran = load_waveform(results / "tran.dat", ["time", "v(n1)", "v(n2)"])
    values = {name: measurement(log, name) for name in ("tper", "frequency", "tpd")}
    check_duration(tran, 10e-9)
    periods = []
    for column in (1, 2):
        edges = crossings(tran, column, True, supply / 2, after=1e-9)
        check(len(edges) >= 6, "Ring did not sustain at least five complete settled cycles")
        node_periods = [b - a for a, b in zip(edges, edges[1:])]
        mean = statistics.mean(node_periods)
        check((max(node_periods) - min(node_periods)) / mean < 0.02,
              "Settled oscillator period varies by more than 2%")
        check(abs(mean - values["tper"]) / mean < 0.02,
              "Oscillator nodes disagree with the measured period")
        for start, stop in zip(edges, edges[1:]):
            samples = [row[column] for row in tran if start <= row[0] <= stop]
            check(min(samples) < 0.1 * supply and max(samples) > 0.9 * supply,
                  "Oscillator output does not approach both rails in every settled cycle")
        if column == 1:
            periods = node_periods
    check(abs(periods[0] - values["tper"]) < 1e-16, "Waveform disagrees with period measurement")
    check(values["tper"] > 0 and 0 < values["tpd"] < 100e-12, "Invalid ring period or stage delay")
    check(math.isclose(values["frequency"], 1 / values["tper"], rel_tol=1e-6)
          and math.isclose(values["tpd"], values["tper"] / 22, rel_tol=1e-6),
          "Ring frequency or per-stage delay is inconsistent with its period")
    notes = [
        f"PASS: {len(tran)} finite transient rows cover startup and 10 ns of oscillation.",
        f"PASS: {len(periods)} settled output cycles after 1 ns; each approaches both rails.",
        "PASS: both observed nodes have stable periods (spread below 2%).",
        "PASS: independent crossings match ngspice; frequency=1/period and stage delay=period/22.",
    ]
    return values, tran, notes


def style_axis(axis, xlabel, supply):
    axis.set(xlabel=xlabel, ylabel="Voltage (V)", ylim=(-0.12 * supply, 1.12 * supply))
    axis.grid(True, alpha=0.25)
    axis.legend(loc="upper right")


def save_plot(figure, path):
    figure.savefig(path, dpi=180)
    plt.close(figure)


def plot_inverter(results, values, dc, tran, model, supply):
    figure, axis = plt.subplots(figsize=(9, 5), layout="constrained")
    axis.plot([row[1] for row in dc], [row[2] for row in dc], label="Output V(out)")
    axis.plot([0, supply], [0, supply], "--", color="0.55", linewidth=1, label="Input = output")
    axis.plot(values["vm"], values["vm"], "o", color="tab:red",
              label=f"Switching voltage: {values['vm']:.3f} V")
    axis.set_title(f"CMOS inverter DC transfer | PTM 45 nm {model.upper()} | VDD = {supply:.1f} V | 27 °C")
    style_axis(axis, "Input voltage (V)", supply)
    save_plot(figure, results / "vtc.png")

    figure, axis = plt.subplots(figsize=(10, 5), layout="constrained")
    time = [row[0] * 1e9 for row in tran]
    axis.plot(time, [row[1] for row in tran], "--", label="Input V(in)")
    axis.plot(time, [row[2] for row in tran], label="Output V(out)")
    axis.set_title(f"CMOS inverter transient | 1 fF load | PTM 45 nm {model.upper()} | VDD = {supply:.1f} V\n"
                   f"tphl = {values['tphl'] * 1e12:.3f} ps, tplh = {values['tplh'] * 1e12:.3f} ps")
    axis.set_xlim(0, 2)
    style_axis(axis, "Time (ns)", supply)
    save_plot(figure, results / "tran.png")


def plot_ring(results, values, tran, model, supply):
    figure, axes = plt.subplots(2, 1, figsize=(10, 7), layout="constrained")
    time = [row[0] * 1e9 for row in tran]
    for axis in axes:
        axis.plot(time, [row[1] for row in tran], label="Output V(n1)", linewidth=1.2)
        style_axis(axis, "Time (ns)", supply)
    stop = tran[-1][0] * 1e9
    axes[0].set(xlim=(0, stop), title="Startup and sustained oscillation")
    axes[1].plot(time, [row[2] for row in tran], "--", label="Next stage V(n2)", linewidth=1.2)
    axes[1].set(xlim=(stop - 2 * values["tper"] * 1e9, stop), title="Final 2 periods")
    axes[1].legend(loc="upper right")
    figure.suptitle(f"11-stage ring oscillator | PTM 45 nm {model.upper()} | VDD = {supply:.1f} V | 27 °C\n"
                   f"Frequency = {values['frequency'] / 1e9:.3f} GHz, "
                   f"per-stage delay = {values['tpd'] * 1e12:.3f} ps")
    save_plot(figure, results / "tran.png")


def run_bench(name, model, executable, version, supply_override=None, condition="nominal"):
    bench = ROOT / name
    model_filename, supply = MODELS[model]
    if supply_override is not None:
        supply = supply_override
    model_path = ROOT.parent / model_filename
    check(model_path.is_file(), f"Missing model card: {model_path}")
    results = bench / "results" / model
    if condition != "nominal":
        results = results / condition
    results.mkdir(parents=True, exist_ok=True)
    # Remove known generated files so a failed run cannot pass using stale data.
    for filename in (f"{name}.log", "vtc.dat", "tran.dat", "vtc.png", "tran.png",
                     "validation.txt", "bsim4.out"):
        (results / filename).unlink(missing_ok=True)
    log_path = results / f"{name}.log"
    # The shared SPICE testbench includes only this selected card and supply.
    (results / "model.inc").write_text(
        f'* Generated configuration: PTM 45nm {model.upper()}\n'
        f'.include "{model_path.as_posix()}"\n.param vdd={supply:.1f}\n')
    print(f"Running {name}/{model} (VDD={supply:.1f} V)...", flush=True)
    process = subprocess.run([executable, "-n", "-b", "-o", str(log_path), str(bench / BENCHES[name])],
                             cwd=results, capture_output=True, text=True, timeout=60)
    check(process.returncode == 0, f"ngspice failed; see {log_path}\n{process.stdout}{process.stderr}")
    log = log_path.read_text()
    check(not re.search(r"\berror\b|\bfatal\b|\bfailed\b|unknown|unrecognized|not found|"
                        r"no such|singular matrix|timestep too small|convergence problem", log, re.I),
          f"ngspice reported an error; see {log_path}")
    warnings = [line.strip() for line in log.splitlines() if line.lstrip().startswith("Warning:")]
    check(all(warning == NGATE_WARNING for warning in warnings),
          f"Unexpected ngspice warning; see {log_path}")
    if name == "inverter":
        values, dc, tran, notes = validate_inverter(results, log, supply)
        plot_inverter(results, values, dc, tran, model, supply)
    else:
        values, tran, notes = validate_ring(results, log, supply)
        plot_ring(results, values, tran, model, supply)
    report = [f"Testbench: {name}/{model}", f"Simulator: {version}",
              f"Model: {model_filename} (BSIM4 version=4.8); VDD={supply:.1f} V; temperature=27 C.",
              f"Measurement threshold: {supply / 2:g} V (50% of VDD).",
              "PASS: ngspice completed without parsing, convergence, or measurement errors.", *notes]
    report.extend(f"{key} = {value:.12g}" for key, value in values.items())
    report.append("PASS: PNG waveform plots saved alongside simulation data.")
    if warnings:
        report.append(f"Known original-card Ngate warning occurred {len(warnings)} times; parameters retained.")
    (results / "validation.txt").write_text("\n".join(report) + "\n")
    print(f"PASS: {name}/{model}; results and PNGs: {results}", flush=True)
    for key, value in values.items():
        print(f"  {key} = {value:.9g}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("example", nargs="?", choices=("all", *BENCHES, "analogcoderpro", *acp.CIRCUITS), default="all")
    parser.add_argument("--model", choices=("all", *MODELS), default="all",
                        help="Device family to simulate (default: all)")
    parser.add_argument("--supply", choices=("nominal", "common", "both"), default="nominal",
                        help="Nominal supplies, common 1.0 V, or both; shared HP case runs once")
    parser.add_argument("--optimize", action="store_true", help="Optimize the selected AnalogCoderPro cases")
    parser.add_argument("--trials", type=int, default=512, help="Maximum candidate evaluations per optimized case")
    parser.add_argument("--seed", type=int, default=42, help="Repeatable optimizer seed")
    args = parser.parse_args()
    executable = shutil.which("ngspice")
    check(executable is not None, "ngspice must be installed and on PATH")
    version_output = subprocess.run([executable, "--version"], check=True,
                                    capture_output=True, text=True).stdout
    version = next(line.strip("* ") for line in version_output.splitlines() if "ngspice-" in line)
    if args.example == "all" or args.example in BENCHES:
        for name in BENCHES if args.example == "all" else (args.example,):
            for model, condition, supply in acp.cases(args.model, args.supply):
                run_bench(name, model, executable, version, supply, condition)
    if args.example in ("all", "analogcoderpro") or args.example in acp.CIRCUITS:
        selected = list(acp.CIRCUITS.values()) if args.example in ("all", "analogcoderpro") else [acp.CIRCUITS[args.example]]
        if not acp.run(selected, args.model, args.supply, args.optimize, args.trials, args.seed):
            sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError, StopIteration) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
