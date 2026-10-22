"""Native-ngspice characterization and bounded optimization of upstream topologies."""
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import differential_evolution
from scipy.stats import qmc

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CATALOG = json.loads((HERE / "catalog.json").read_text())
CIRCUITS = {item["id"]: item for item in CATALOG["circuits"]}
NGATE = "Warning: Ngate = 1e+17 is less than 1.E18cm^-3."
ERROR = re.compile(r"\berror\b|\bfatal\b|\bfailed\b|unknown parameter|unrecognized|"
                   r"not found|no such|singular matrix|timestep too small", re.I)


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def read_data(path):
    header = path.read_text().splitlines()[0].split()
    array = np.loadtxt(path, skiprows=1, ndmin=2)
    if array.shape[1] != len(header) or not np.isfinite(array).all():
        raise ValueError(f"Invalid waveform: {path}")
    if len(array) > 1 and not np.all(np.diff(array[:, 0]) > 0):
        raise ValueError(f"Non-increasing waveform scale: {path}")
    return {name: array[:, index] for index, name in enumerate(header)}


def edges(time, wave, threshold, rising):
    before, after = wave[:-1] - threshold, wave[1:] - threshold
    indices = np.flatnonzero((before < 0) & (after >= 0) if rising else (before > 0) & (after <= 0))
    return time[indices] + np.diff(time)[indices] * (-before[indices]) / (after[indices] - before[indices])


def analyses(circuit, supply, full):
    family = circuit["family"]
    output = f"v({circuit['output']})"
    devices = circuit["devices"]
    save = " ".join(f"@{d['name']}[id]" for d in devices)
    op_nodes = " ".join(f"v({name})" for name in circuit["nodes"])
    op_quantities = " ".join(f"@{d['name']}[{q}]" for d in devices for q in ("id", "gm", "gds"))
    commands = [".control", "set noaskquit", "set numdgt=12", "set wr_singlescale", "set wr_vecnames",
                f"save all {save}", "op", f"let out = {output}", "let power = -v(vdd)*i(vdd)",
                f"wrdata op.dat out power {op_nodes} {op_quantities}"]
    if family == "amplifier":
        commands += ["ac dec 24 1k 100G", f"let out_re = real({output})",
                     f"let out_im = imag({output})", "wrdata ac.dat out_re out_im"]
        if circuit["differential"]:
            commands += ["alter vinn acphase = 0", "ac lin 1 1k 1k",
                         f"let cm_re = real({output})*2", f"let cm_im = imag({output})*2",
                         "wrdata common_mode.dat cm_re cm_im", "alter vinn acphase = 180"]
        if full:
            vin = "v(vinp)-v(vinn)" if circuit["differential"] else "v(vin)"
            sweep_source = "vinp" if circuit["differential"] else "vin"
            commands += ["tran 5n 5u 0 5n", f"let input_signal = {vin}", f"let out = {output}",
                         "let power = -v(vdd)*i(vdd)", "wrdata tran.dat input_signal out power",
                         f"dc {sweep_source} 0 {supply:.12g} {supply/100:.12g}",
                         f"let input_signal = v({'vinp' if circuit['differential'] else 'vin'})",
                         f"let out = {output}", "wrdata dc.dat input_signal out"]
    elif family == "inverter":
        commands += [f"dc vin 0 {supply:.12g} {supply/100:.12g}", "let input_signal = v(vin)",
                     "let out = v(vout)", "let power = -v(vdd)*i(vdd)",
                     "wrdata dc.dat input_signal out power", "tran 1p 2n 0 1p",
                     "let input_signal = v(vin)", "let out = v(vout)",
                     "let power = -v(vdd)*i(vdd)", "wrdata tran.dat input_signal out power"]
    elif family == "current":
        device = devices[-1]["name"] if circuit["task"] == 17 else devices[0]["name"]
        commands += [f"dc vforce 0 {supply:.12g} {supply/100:.12g}",
                     f"let out = {output}", f"let current = @{device}[id]",
                     "wrdata dc.dat out current"]
    else:
        stop, step = (1.2e-6, 50e-12) if full else (300e-9, 100e-12)
        commands += [f"tran {step:.12g} {stop:.12g} 0 {step:.12g}",
                     "let rf = v(vrfp)-v(vrfn)", "let lo = v(vlop)-v(vlon)",
                     "let out = v(voutp)-v(voutn)", "let power = -v(vdd)*i(vdd)",
                     "wrdata tran.dat rf lo out power"]
    return "\n".join(commands + ["quit", ".endc", ""])


def execute(circuit, model, supply, parameters, folder, executable, full=False):
    folder.mkdir(parents=True, exist_ok=True)
    model_path = ROOT / f"45nm_{model.upper()}_ngspice.pm"
    (folder / "model.inc").write_text(f'.include "{model_path}"\n.param vdd={supply:.12g}\n')
    (folder / "parameters.inc").write_text("\n".join(f".param {k}={v:.16g}" for k, v in parameters.items()) + "\n")
    (folder / "analysis.inc").write_text(analyses(circuit, supply, full))
    source = HERE / circuit["directory"] / "testbench.cir"
    # This generated wrapper also makes the selected circuit directly runnable.
    (folder / "best.cir").write_text(f'* {circuit["id"]} {model.upper()} at {supply:g} V\n.include "{source}"\n')
    process = subprocess.run([executable, "-n", "-b", "-o", "simulation.log", "best.cir"],
                             cwd=folder, capture_output=True, text=True, timeout=30)
    log = (folder / "simulation.log").read_text()
    if process.returncode or ERROR.search(log):
        raise ValueError("ngspice error: " + " ".join(line for line in log.splitlines()
                         if re.search(r"error|failed|fatal|unknown|not found", line, re.I))[:500])
    warnings = [line.strip() for line in log.splitlines() if line.strip().startswith("Warning:")]
    if any(line != NGATE for line in warnings):
        raise ValueError("Unexpected model warning: " + "; ".join(sorted(set(warnings))))
    data = {path.stem: read_data(path) for path in folder.glob("*.dat")}
    return data, len(warnings)


def characterize(circuit, supply, data):
    """Return measured values and dimensionless, nonnegative floor violations."""
    op = data["op"]
    power = float(op["power"][0])
    metrics = {"output_bias_v": float(op["out"][0]), "power_w": power}
    violations = {}
    # Include every source, drain, bulk, and gate node in the rail check.
    voltages = [float(op[f"v({node})"][0]) for node in circuit["nodes"]]
    violations["node_rails"] = max(0, -min(voltages) / supply - .001,
                                    max(voltages) / supply - 1.001)
    currents = [abs(float(op[f"@{d['name']}[id]"][0])) for d in circuit["devices"]]
    metrics["minimum_device_current_a"] = min(currents)
    family = circuit["family"]
    if family == "amplifier":
        ac = data["ac"]
        frequency = next(iter(ac.values()))
        transfer = ac["out_re"] + 1j * ac["out_im"]
        magnitude = np.abs(transfer)
        gain = float(magnitude[0])
        indices = np.flatnonzero(magnitude <= gain / math.sqrt(2))
        bandwidth = float(frequency[-1])
        if len(indices) and indices[0] > 0:
            k = indices[0]
            fraction = ((gain / math.sqrt(2)) - magnitude[k-1]) / (magnitude[k] - magnitude[k-1])
            bandwidth = float(np.exp(np.log(frequency[k-1]) + fraction * np.log(frequency[k] / frequency[k-1])))
        cmrr = None
        if circuit["differential"]:
            cm = data["common_mode"]
            common_gain = math.hypot(float(cm["cm_re"][0]), float(cm["cm_im"][0]))
            cmrr = 20 * math.log10(max(gain, 1e-30) / max(common_gain, 1e-30))
            violations["cmrr_20db"] = max(0, (20 - cmrr) / 20)
            metrics["common_mode_gain_v_v"] = common_gain
        floor = .5 if circuit["task"] == 3 else 2
        violations.update(gain_floor=max(0, (floor - gain) / floor),
                          bandwidth_1mhz=max(0, 1 - bandwidth / 1e6),
                          output_headroom=max(0, .02 - metrics["output_bias_v"] / supply,
                                              metrics["output_bias_v"] / supply - .98),
                          conducting_devices=max(0, 1 - min(currents) / 1e-12))
        metrics.update(gain_v_v=gain, gain_db=20*math.log10(max(gain, 1e-30)),
                       bandwidth_hz=bandwidth, bandwidth_is_lower_bound=not bool(len(indices)),
                       gbw_hz=gain*bandwidth, cmrr_db=cmrr,
                       fom=gain*bandwidth/max(power, 1e-30))
        if "tran" in data:
            tran = data["tran"]
            time = next(iter(tran.values()))
            mask = time >= 3e-6
            x = tran["input_signal"][mask]
            y = tran["out"][mask]
            basis = np.column_stack([np.sin(2*np.pi*1e6*time[mask]),
                                     np.cos(2*np.pi*1e6*time[mask]), np.ones(mask.sum())])
            fit_in = np.linalg.lstsq(basis, x, rcond=None)[0]
            fit_out = np.linalg.lstsq(basis, y, rcond=None)[0]
            measured = math.hypot(*fit_out[:2]) / max(math.hypot(*fit_in[:2]), 1e-30)
            expected = float(np.interp(np.log(1e6), np.log(frequency), magnitude))
            metrics["transient_gain_v_v"] = measured
            metrics["transient_ac_relative_error"] = abs(measured-expected)/max(expected, 1e-30)
            metrics["output_swing_v"] = float(np.ptp(data["dc"]["out"]))
            violations["transient_ac_agreement_10pct"] = max(0, metrics["transient_ac_relative_error"]/.1-1)
    elif family == "inverter":
        dc, tran = data["dc"], data["tran"]
        time = next(iter(tran.values()))
        vin, vout = tran["input_signal"], tran["out"]
        metrics.update(voh_v=float(dc["out"][0]), vol_v=float(dc["out"][-1]),
                       static_high_power_w=float(dc["power"][0]), static_low_power_w=float(dc["power"][-1]))
        difference = dc["out"] - dc["input_signal"]
        crossings = np.flatnonzero(difference[:-1] * difference[1:] <= 0)
        metrics["switching_voltage_v"] = None
        if len(crossings):
            k = crossings[0]
            metrics["switching_voltage_v"] = float(np.interp(0, [difference[k+1], difference[k]],
                                                          [dc["input_signal"][k+1], dc["input_signal"][k]]))
        for name, rising in (("tphl_s", False), ("tplh_s", True)):
            ins = edges(time, vin, supply/2, not rising)
            outs = edges(time, vout, supply/2, rising)
            delay = float(outs[0]-ins[0]) if len(ins) and len(outs) else None
            metrics[name] = delay
            violations[name] = 0 if delay is not None and 0 < delay < 250e-12 else 1
        for name, rising in (("rise_time_s", True), ("fall_time_s", False)):
            early = edges(time, vout, supply*(.1 if rising else .9), rising)
            late = edges(time, vout, supply*(.9 if rising else .1), rising)
            metrics[name] = float(late[0]-early[0]) if len(early) and len(late) else None
        mask = time >= 1e-9
        power = float(np.trapezoid(tran["power"][mask], time[mask]) / (time[mask][-1]-time[mask][0]))
        energy = power / 2e9
        delay = np.mean([v for v in (metrics["tphl_s"], metrics["tplh_s"]) if v is not None]) if any(
            v is not None for v in (metrics["tphl_s"], metrics["tplh_s"])) else 1
        metrics.update(power_w=power, energy_per_transition_j=energy, edp_j_s=float(energy*delay),
                       fom=float(1/max(energy*delay, 1e-40)))
        violations["logic_rails_5pct"] = max(0, abs(metrics["voh_v"]-supply)/supply/.05-1,
                                             abs(metrics["vol_v"])/supply/.05-1)
        for start, end, level in ((.35e-9, .55e-9, 0), (.85e-9, 1.05e-9, supply),
                                   (1.35e-9, 1.55e-9, 0), (1.85e-9, 2e-9, supply)):
            values = vout[(time >= start) & (time <= end)]
            violations["settled_logic"] = max(violations.get("settled_logic", 0),
                                               max(0, float(np.max(np.abs(values-level)))/supply/.05-1))
    elif family == "current":
        dc = data["dc"]
        voltage, current = dc["out"], dc["current"]
        value = float(np.interp(.7*supply, voltage, current))
        mask = (voltage >= .5*supply-1e-12) & (voltage <= .9*supply+1e-12)
        tracking = abs(value-10e-6)/10e-6
        regulation = float(np.ptp(current[mask]))/max(abs(value), 1e-30)
        slope = float(np.polyfit(voltage[mask], current[mask], 1)[0])
        compliant = voltage[(current >= 9e-6) & (current <= 11e-6)]
        # Vforce is a compliance-test fixture. Charge output current to VDD,
        # including the fixed 10 uA reference branch for the cascode mirror.
        power = supply * (max(value, 0) + (10e-6 if circuit["task"] == 17 else 0))
        metrics.update(current_a=value, tracking_error=tracking, regulation=regulation,
                       output_resistance_ohm=1/max(abs(slope), 1e-30),
                       compliance_v=float(compliant[0]) if len(compliant) else None,
                       power_w=power, fom=1/max(power*(tracking+regulation+.001), 1e-30))
        violations.update(tracking_10pct=max(0, tracking/.1-1), regulation_20pct=max(0, regulation/.2-1))
    else:
        tran = data["tran"]
        violations["lo_input_rails"] = max(0, .05/supply-float(op["v(vlop)"][0])/supply,
                                           float(op["v(vlop)"][0])/supply+.05/supply-1)
        time = next(iter(tran.values()))
        duration = 1e-6 if time[-1] > 1e-6 else 250e-9
        dt = 50e-12 if duration > 250e-9 else 100e-12
        grid = time[-1] - duration + np.arange(round(duration/dt))*dt
        signal = np.interp(grid, time, tran["out"])
        window = np.hanning(len(signal))
        spectrum = 2*np.abs(np.fft.rfft((signal-signal.mean())*window))/window.sum()
        frequency = np.fft.rfftfreq(len(signal), dt)
        down = float(spectrum[np.argmin(abs(frequency-20e6))])
        up = float(spectrum[np.argmin(abs(frequency-220e6))])
        gain = down/.025
        power_signal = np.interp(grid, time, tran["power"])
        power = float(np.mean(power_signal))
        feedthrough = max(float(spectrum[np.argmin(abs(frequency-f))]) for f in (100e6, 120e6))
        metrics.update(conversion_gain_v_v=gain, conversion_gain_db=20*math.log10(max(gain, 1e-30)),
                       if_down_v=down, if_up_v=up, feedthrough_v=feedthrough,
                       power_w=power, fom=gain/max(power, 1e-30))
        violations.update(conversion_gain_0db=max(0, 1-gain),
                          mixing_products=max(0, 1-down/1e-6, 1-up/1e-6))
        data["fft"] = {"frequency": frequency, "amplitude": spectrum}
    violations["positive_supply_power"] = 0 if metrics["power_w"] > 1e-15 else 1
    return metrics, {key: float(value) for key, value in violations.items() if value > 1e-8}


def objective(metrics, violations):
    if violations:
        return 1000 + sum(min(value, 1e6) for value in violations.values())
    return -math.log10(max(metrics["fom"], 1e-40))


def decode(circuit, vector):
    result = {}
    index = 0
    for name, spec in circuit["parameters"].items():
        if spec.get("fixed"):
            result[name] = spec["initial"]
        else:
            fraction = float(vector[index])
            result[name] = (spec["low"] + fraction*(spec["high"]-spec["low"]) if spec["kind"] == "bias"
                            else math.exp(math.log(spec["low"])+fraction*math.log(spec["high"]/spec["low"])))
            index += 1
    return result


def initial_vector(circuit):
    return np.array([(spec["initial"]-spec["low"])/(spec["high"]-spec["low"]) if spec["kind"] == "bias"
                     else math.log(spec["initial"]/spec["low"])/math.log(spec["high"]/spec["low"])
                     for spec in circuit["parameters"].values() if not spec.get("fixed")])


def optimize(circuit, model, supply, folder, executable, trials, seed):
    lock = threading.Lock()
    counter = 0
    best = None
    history = folder / "optimization.jsonl"
    history.write_text("")
    scratch = folder / "search"
    scratch.mkdir(exist_ok=True)

    def evaluate(vector):
        nonlocal counter, best
        with lock:
            if counter >= trials:
                return 1e12
            counter += 1
            index = counter
        parameters = decode(circuit, vector)
        record = dict(trial=index, parameters=parameters)
        try:
            with tempfile.TemporaryDirectory(dir=scratch) as temp:
                data, _ = execute(circuit, model, supply, parameters, Path(temp), executable)
                metrics, violations = characterize(circuit, supply, data)
            loss = objective(metrics, violations)
            record.update(loss=loss, metrics=metrics, violations=violations)
        except (ValueError, OSError, subprocess.SubprocessError, KeyError, IndexError) as error:
            loss = 1e9
            record.update(loss=loss, error=str(error))
        with lock:
            with history.open("a") as stream:
                stream.write(json.dumps(record, allow_nan=False) + "\n")
            if "metrics" in record and (best is None or
                    (loss, tuple(parameters.values())) < (best["loss"], tuple(best["parameters"].values()))):
                best = record
        return loss

    dimension = len(initial_vector(circuit))
    # Fixed population and deferred updates give reproducible results even
    # though independent ngspice evaluations run in four isolated directories.
    size = min(64, trials)
    population = qmc.Sobol(dimension, scramble=True, seed=seed).random_base2(6)[:size]
    population[0] = initial_vector(circuit)
    # Bias the first quarter of the population towards minimum drawn length.
    length_indices = [i for i, spec in enumerate(s for s in circuit["parameters"].values()
                                                if not s.get("fixed")) if spec["kind"] == "length"]
    population[:size//4, length_indices] = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        differential_evolution(evaluate, [(0, 1)]*dimension, init=population,
                               maxiter=math.ceil(trials/size)-1, seed=seed,
                               tol=0, atol=0, polish=False, updating="deferred", workers=pool.map)
    # Consume the remaining budget if an identical-penalty population converged.
    if counter < trials:
        extra = qmc.Sobol(dimension, scramble=True, seed=seed+1).random_base2(math.ceil(math.log2(trials)))
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(evaluate, extra[:trials-counter]))
    scratch.rmdir()
    if best is None:
        raise ValueError(f"No measurable candidate in {counter} trials; see {history}")
    best.update(trials=counter, seed=seed, algorithm="SciPy differential evolution; bounded Sobol completion")
    write_json(folder / "best.json", best)
    return best


def plot_case(circuit, model, supply, folder, data, metrics):
    label = circuit["label"].replace("_", " ")
    title = f"AnalogCoderPro p{circuit['task']:02d}: {label} | {model.upper()} | {supply:g} V | 27 °C"

    def save(fig, name):
        fig.suptitle(title)
        for axis in fig.axes:
            axis.grid(alpha=.25)
        fig.savefig(folder / name, dpi=160)
        plt.close(fig)

    if "dc" in data:
        dc = data["dc"]
        fig, axis = plt.subplots(figsize=(9, 5), layout="constrained")
        if circuit["family"] == "current":
            axis.plot(dc["out"], dc["current"]*1e6)
            axis.axhline(10, linestyle="--", color="grey", label="10 µA target")
            axis.set(xlabel="Output voltage (V)", ylabel="Drain current (µA)")
            axis.legend()
        else:
            axis.plot(dc["input_signal"], dc["out"])
            axis.set(xlabel="Swept input voltage (V)", ylabel="Output voltage (V)")
        save(fig, "dc.png")
    if "ac" in data:
        ac = data["ac"]
        frequency = next(iter(ac.values()))
        transfer = ac["out_re"]+1j*ac["out_im"]
        fig, axes = plt.subplots(2, 1, figsize=(9, 7), layout="constrained")
        axes[0].semilogx(frequency, 20*np.log10(np.maximum(abs(transfer), 1e-30)))
        axes[0].set(ylabel="Gain (dB)")
        axes[1].semilogx(frequency, np.unwrap(np.angle(transfer))*180/np.pi)
        axes[1].set(xlabel="Frequency (Hz)", ylabel="Phase (degrees)")
        save(fig, "ac.png")
    if "tran" in data:
        tran = data["tran"]
        time = next(iter(tran.values()))
        fig, axes = plt.subplots(2, 1, figsize=(10, 7), layout="constrained")
        factor, unit = (1e9, "ns") if circuit["family"] == "inverter" else (1e6, "µs")
        if circuit["family"] == "mixer":
            axes[0].plot(time*factor, tran["rf"], label="Differential RF")
            axes[0].plot(time*factor, tran["lo"], label="Differential LO", alpha=.7)
            axes[0].set_xlim(max(0, time[-1]*factor-.1), time[-1]*factor)
            axes[0].legend()
        else:
            axes[0].plot(time*factor, tran["input_signal"], label="Input")
        axes[1].plot(time*factor, tran["out"], label="Output")
        for axis in axes:
            axis.set(xlabel=f"Time ({unit})", ylabel="Voltage (V)")
            axis.legend()
        save(fig, "tran.png")
    if "fft" in data:
        fft = data["fft"]
        fig, axis = plt.subplots(figsize=(10, 5), layout="constrained")
        axis.plot(fft["frequency"]/1e6, 20*np.log10(np.maximum(fft["amplitude"], 1e-15)))
        for frequency in (20, 220):
            axis.axvline(frequency, color="tab:red", alpha=.6, linestyle="--")
        axis.set(xlabel="Frequency (MHz)", ylabel="Differential amplitude (dBV)", xlim=(0, 350))
        save(fig, "fft.png")
        np.savetxt(folder / "fft.dat", np.column_stack(list(fft.values())),
                   header="frequency_hz amplitude_v", comments="")


def verify_case(circuit, model, condition, supply, parameters, folder, executable, metadata):
    # Every verification reruns ngspice; optimizer waveforms are never reused.
    for filename in ("metrics.json", "validation.txt", "op.dat", "ac.dat", "common_mode.dat",
                     "dc.dat", "tran.dat", "fft.dat", "dc.png", "ac.png", "tran.png", "fft.png"):
        (folder / filename).unlink(missing_ok=True)
    data, warnings = execute(circuit, model, supply, parameters, folder, executable, full=True)
    metrics, violations = characterize(circuit, supply, data)
    status = "LIMITED" if violations else "PASS"
    plots = (['dc.png', 'ac.png', 'tran.png'] if circuit["family"] == "amplifier" else
             ['dc.png'] if circuit["family"] == "current" else
             ['dc.png', 'tran.png'] if circuit["family"] == "inverter" else ['tran.png', 'fft.png'])
    plot_case(circuit, model, supply, folder, data, metrics)
    for name in plots:
        if not (folder / name).is_file():
            raise ValueError(f"Missing plot: {name}")
    simulator = subprocess.check_output([executable, "--version"], text=True)
    version = next(line.strip("* ") for line in simulator.splitlines() if "ngspice-" in line)
    model_path = ROOT / f"45nm_{model.upper()}_ngspice.pm"
    record = dict(id=circuit["id"], task=circuit["task"], label=circuit["label"], family=circuit["family"],
                  model=model, condition=condition, supply_v=supply, temperature_c=27, status=status,
                  metrics=metrics, violations=violations, parameters=parameters, plots=plots,
                  upstream_revision=CATALOG["revision"], upstream_source=circuit["source"],
                  upstream_source_sha256=circuit["source_sha256"], simulator=version,
                  model_sha256=hashlib.sha256(model_path.read_bytes()).hexdigest(),
                  source_sha256=hashlib.sha256((HERE/circuit["directory"]/"testbench.cir").read_bytes()).hexdigest(),
                  optimization=metadata)
    write_json(folder / "metrics.json", record)
    lines = [f"Status: {status}", f"Circuit: {circuit['id']} ({circuit['label']})", f"Simulator: {version}",
             f"Model: {model.upper()}, VDD={supply:g} V, temperature=27 C; {condition}.",
             f"Upstream: {CATALOG['revision']} / {circuit['source']}",
             "PASS: independent ngspice rerun; all exported data finite and scales increasing.",
             "PASS: response PNGs regenerated from this verification run."]
    lines += [f"{key} = {value}" for key, value in metrics.items()]
    lines += [f"LIMITED: {key}; normalized violation={value:.6g}" for key, value in violations.items()]
    lines += [f"Known original-card Ngate warning: {warnings} occurrences.",
              "Optimization results are best found within the stated budget, not global optima."]
    (folder / "validation.txt").write_text("\n".join(lines)+"\n")
    return record


def cases(model, supply_mode):
    families = ("hp", "lp") if model == "all" else (model,)
    result = []
    for family in families:
        if supply_mode in ("nominal", "both") or family == "hp":
            result.append((family, "nominal", 1.0 if family == "hp" else 1.1))
        if family == "lp" and supply_mode in ("common", "both"):
            result.append((family, "common_1v", 1.0))
    return result


def summarize():
    target = HERE / "results"
    target.mkdir(exist_ok=True)
    records = []
    for circuit in CIRCUITS.values():
        for path in (HERE / circuit["directory"] / "results").glob("*/*/metrics.json"):
            record = json.loads(path.read_text())
            record["results_path"] = str(path.parent.relative_to(HERE))
            records.append(record)
    records.sort(key=lambda r: (r["task"], r["model"], r["condition"]))
    write_json(target / "metrics.json", records)
    metric_keys = sorted({key for r in records for key in r.get("metrics", {})})
    common_fields = ["id", "label", "family", "model", "condition", "supply_v", "status", "results_path"]
    fields = common_fields + ["parameters_json", "violations_json", "trials", "seed"] + metric_keys
    with (target / "comparison.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow({**{key: record.get(key) for key in common_fields},
                "parameters_json": json.dumps(record.get("parameters", {})),
                "violations_json": json.dumps(record.get("violations", {})),
                "trials": record.get("optimization", {}).get("trials"),
                "seed": record.get("optimization", {}).get("seed"), **record.get("metrics", {})})
    text = ["# AnalogCoderPro PTM 45nm comparison", "",
            "Independent HP/LP sizing and bias optimization. Best found within the recorded search budget.",
            "HP at 1.0 V is shared by the nominal-supply and common-1.0-V comparisons.", ""]
    for mode, title in (("nominal", "Nominal supplies: HP 1.0 V / LP 1.1 V"),
                        ("common_1v", "Common supply: HP and LP 1.0 V")):
        text += [f"## {title}", "", f"![Comparison]({mode}.png)", "",
                 "| Task | Model / supply | Status | Power (µW) | Efficiency FoM | Results |",
                 "| --- | --- | --- | ---: | ---: | --- |"]
        for record in records:
            if record["condition"] != ("nominal" if record["model"] == "hp" else mode):
                continue
            m = record.get("metrics", {})
            path = "../" + record["results_path"]
            links = [f"[validation]({path}/validation.txt)", f"[parameters]({path}/parameters.inc)"]
            links += [f"[{name}]({path}/{name})" for name in record.get("plots", [])]
            power_text = f"{m['power_w']*1e6:.4g}" if "power_w" in m else "—"
            fom_text = f"{m['fom']:.4g}" if record["status"] == "PASS" else "—"
            text.append(f"| {record['id']} {record['label']} | {record['model'].upper()} / {record['supply_v']:g} V | "
                        f"{record['status']} | {power_text} | {fom_text} | {', '.join(links)} |")
        text.append("")
    text += ["", "FoMs have different definitions by circuit family; compare them within each task only.",
             "LIMITED means the measured candidate did not meet all performance floors; it is not a PASS.", ""]
    (target / "comparison.md").write_text("\n".join(text))
    for mode in ("nominal", "common_1v"):
        fig, axes = plt.subplots(2, 1, figsize=(13, 8), layout="constrained")
        for model, offset, color in (("hp", -.18, "tab:blue"), ("lp", .18, "tab:orange")):
            selected = [next((r for r in records if r["id"] == name and r["model"] == model
                            and r["condition"] == ("nominal" if model == "hp" else mode)), None)
                        for name in CIRCUITS]
            for index, record in enumerate(selected):
                if not record or record["status"] == "FAIL":
                    continue
                metrics = record["metrics"]
                axes[0].bar(index+offset, max(metrics["power_w"]*1e6, 1e-9), .34, color=color,
                            hatch="//" if record["status"] == "LIMITED" else None)
                reference = next((r for r in records if r["id"] == record["id"] and r["model"] == "hp"
                                  and r["condition"] == "nominal" and r["status"] != "FAIL"), None)
                if reference and reference["status"] == record["status"] == "PASS":
                    ratio = metrics["fom"]/max(reference["metrics"]["fom"], 1e-300)
                    axes[1].bar(index+offset, max(ratio, 1e-12), .34, color=color,
                                hatch="//" if record["status"] == "LIMITED" else None)
        axes[0].set(ylabel="Supply power (µW)", yscale="log")
        axes[1].set(ylabel="Efficiency FoM / HP FoM (PASS cases)", yscale="log")
        for axis in axes:
            axis.set_xticks(range(len(CIRCUITS)), [name.removeprefix("acp_") for name in CIRCUITS], rotation=45)
            axis.grid(axis="y", alpha=.2)
        from matplotlib.patches import Patch
        axes[0].legend(handles=[Patch(color="tab:blue", label="HP 1.0 V"),
                                Patch(color="tab:orange", label="LP 1.1 V" if mode == "nominal" else "LP 1.0 V"),
                                Patch(facecolor="white", hatch="//", label="LIMITED: performance floors unmet")])
        fig.suptitle(f"PTM 45nm AnalogCoderPro — {'nominal supplies' if mode == 'nominal' else 'common 1.0 V'}\n"
                     "Independently optimized circuits; FoM definitions differ between tasks")
        fig.savefig(target / f"{mode}.png", dpi=160)
        plt.close(fig)
    counts = {status: sum(r["status"] == status for r in records) for status in ("PASS", "LIMITED", "FAIL")}
    print(f"AnalogCoderPro summary: {counts}; report: {target / 'comparison.md'}", flush=True)
    return records


def run(selected, model, supply_mode, do_optimize=False, trials=512, seed=42):
    executable = shutil.which("ngspice")
    if executable is None:
        raise ValueError("ngspice must be on PATH")
    if trials < 8:
        raise ValueError("At least 8 optimization trials are required")
    failed = False
    for circuit in selected:
        baseline_path = HERE / circuit["directory"] / "parameters.json"
        baselines = json.loads(baseline_path.read_text()) if baseline_path.exists() else {}
        for family, condition, supply in cases(model, supply_mode):
            key = f"{family}/{condition}"
            folder = HERE / circuit["directory"] / "results" / key
            folder.mkdir(parents=True, exist_ok=True)
            for path in list(folder.glob("*.png")) + [folder/"metrics.json", folder/"validation.txt"]:
                path.unlink(missing_ok=True)
            if do_optimize:
                (folder / "best.json").unlink(missing_ok=True)
            print(f"{'Optimizing' if do_optimize else 'Verifying'} {circuit['id']}/{key} at {supply:g} V...", flush=True)
            try:
                if do_optimize:
                    best = optimize(circuit, family, supply, folder, executable, trials, seed)
                    parameters = best["parameters"]
                    metadata = {k: best[k] for k in ("trials", "seed", "algorithm")}
                else:
                    if key not in baselines:
                        raise ValueError(f"Missing selected parameters for {key}; run --optimize first")
                    selection = baselines[key]
                    expected_source = hashlib.sha256((HERE/circuit["directory"]/"testbench.cir").read_bytes()).hexdigest()
                    expected_model = hashlib.sha256((ROOT/f"45nm_{family.upper()}_ngspice.pm").read_bytes()).hexdigest()
                    if (selection["source_sha256"] != expected_source or selection["model_sha256"] != expected_model
                            or selection["upstream_revision"] != CATALOG["revision"]
                            or not math.isclose(selection["supply_v"], supply)):
                        raise ValueError("Selected parameters refer to different circuit/model sources; rerun optimization")
                    parameters = selection["parameters"]
                    metadata = selection["optimization"]
                record = verify_case(circuit, family, condition, supply, parameters, folder, executable, metadata)
                print(f"{record['status']}: {circuit['id']}/{key}; "
                      f"power={record['metrics']['power_w']*1e6:.4g} µW; "
                      f"floors unmet={list(record['violations'])}", flush=True)
            except (ValueError, OSError, subprocess.SubprocessError, KeyError, IndexError) as error:
                failed = True
                write_json(folder / "metrics.json", dict(id=circuit["id"], task=circuit["task"],
                    label=circuit["label"], family=circuit["family"], model=family, condition=condition,
                    supply_v=supply, status="FAIL", error=str(error), metrics={}, plots=[]))
                (folder / "validation.txt").write_text(f"FAIL: {error}\n")
                print(f"FAIL: {circuit['id']}/{key}: {error}", flush=True)
    summarize()
    return not failed
