#!/usr/bin/env python3
"""Translate the pinned upstream construction calls without importing PySpice."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1] / "AnalogCoderPro"
REVISION = "05542af46020e5c37d5a7e3ca79da9f24626e1c9"
TASKS = {
    1: ("common_source", "amplifier"), 2: ("three_stage", "amplifier"),
    3: ("source_follower", "amplifier"), 4: ("common_gate", "amplifier"),
    5: ("cascode_amplifier", "amplifier"), 6: ("resistive_inverter", "inverter"),
    7: ("cmos_inverter", "inverter"), 8: ("current_source", "current"),
    14: ("miller_amplifier", "amplifier"), 15: ("diode_load", "amplifier"),
    16: ("active_load_differential", "amplifier"), 17: ("cascode_mirror", "current"),
    18: ("resistive_differential", "amplifier"), 19: ("gilbert_mixer", "mixer"),
    20: ("two_stage_differential", "amplifier"), 21: ("telescopic", "amplifier"),
}


def number(node, variables):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return variables[node.id]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.MatMult):
        scale = {"u_V": 1, "u_kΩ": 1e3, "u_kOhm": 1e3, "u_pF": 1e-12,
                 "u_nF": 1e-9, "u_uA": 1e-6}[node.right.id]
        return number(node.left, variables) * scale
    raise ValueError(ast.dump(node))


def node_name(node):
    if isinstance(node, ast.Attribute) and node.attr == "gnd":
        return "0"
    name = node.value.lower()
    return "0" if name == "gnd" else name


def translate(task, label, family):
    path = f"sample_design/p{task}/p{task}.py"
    source = (REPO / path).read_text()
    tree = ast.parse(source)
    variables, params, devices, nodes, sources = {}, {}, [], set(), []
    lines = []

    def parameter(name, kind, initial):
        limits = {"width": (90e-9, 20e-6), "length": (45e-9, 450e-9),
                  "resistor": (100, 1e7), "capacitor": (1e-15, 1e-11),
                  "bias": (0.02, 0.98)}
        lo, hi = limits[kind]
        params.setdefault(name, dict(kind=kind, low=lo, high=hi,
                                     initial=max(lo, min(hi, initial))))
        return "{" + name + "}"

    # Only initial DUT construction is imported; p19's later balanced filter
    # pairs are added separately, without executing its source redefinitions.
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "simulator" for t in statement.targets):
                break
            for target in statement.targets:
                if isinstance(target, ast.Name):
                    try:
                        variables[target.id] = number(statement.value, variables)
                    except (KeyError, ValueError):
                        pass
        if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
            continue
        call = statement.value
        fn = call.func
        if not (isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name)
                and fn.value.id == "circuit" and fn.attr in ("MOSFET", "R", "C", "V", "I")):
            continue
        args, kwargs = call.args, {kw.arg: kw.value for kw in call.keywords}
        original_name = args[0].value.lower()
        pins = [node_name(arg) for arg in args[1:5 if fn.attr == "MOSFET" else 3]]
        nodes.update(pin for pin in pins if pin != "0")
        if fn.attr == "MOSFET":
            polarity = "pmos" if "pmos" in kwargs["model"].value else "nmos"
            width = number(kwargs["w"], variables) if "w" in kwargs else 10e-6
            group = polarity[0] + str(round(width * 1e6))
            w = parameter("w" + group, "width", width * 45e-9 / 1e-6)
            length = parameter("l" + group, "length", 45e-9)
            name = original_name if original_name.startswith("m") else "m" + original_name
            lines.append(f"{name} {' '.join(pins)} {polarity} W={w} L={length}")
            devices.append(dict(name=name, pins=pins, polarity=polarity, group=group))
        elif fn.attr in ("R", "C"):
            value = number(args[3], variables)
            if fn.attr == "R":
                # Equal original resistor values remain a matched group.
                name = "r" + str(round(value))
                expr = parameter(name, "resistor", value)
            else:
                expr = parameter("cc", "capacitor", value / 100)
            lines.append(f"{fn.attr.lower()}{original_name} {' '.join(pins)} {expr}")
        elif fn.attr == "V":
            if pins[0] == "vdd":
                continue
            if pins[0] in ("vin", "vinp", "vinn", "vrfp", "vrfn", "vlop", "vlon"):
                continue
            bias = "b" + str(1 + len(sources))
            value = float(number(args[3], variables)) / 5
            parameter(bias, "bias", value)
            sources.append(("v" + original_name, pins, bias))
        elif fn.attr == "I":
            lines.append(f"i{original_name} {' '.join(pins)} 10u")
    for name, pins, bias in sources:
        lines.append(f"{name} {' '.join(pins)} {{{bias}*vdd}}")

    differential = task in (16, 18, 20, 21)
    output = "iout" if task == 17 else "vout"
    stimulus = ["Vdd vdd 0 {vdd}"]
    if family == "amplifier":
        parameter("bin", "bias", 0.75 if differential or task == 3 else 0.55)
        if differential:
            stimulus += ["vinp vinp 0 DC {bin*vdd} AC 0.5 SIN({bin*vdd} 5u 1Meg)",
                         "vinn vinn 0 DC {bin*vdd} AC 0.5 180 SIN({bin*vdd} -5u 1Meg)"]
        else:
            stimulus.append("vin vin 0 DC {bin*vdd} AC 1 SIN({bin*vdd} 10u 1Meg)")
        stimulus.append(f"cexternal {output} 0 1f")
    elif family == "inverter":
        stimulus += ["vin vin 0 PULSE(0 {vdd} 100p 20p 20p 480p 1n)", "cexternal vout 0 1f"]
    elif family == "current":
        stimulus.append(f"vforce {output} 0 {{0.7*vdd}}")
        # The imported resistor is retained as a fixture, not a tuning knob.
        for p in params.values():
            if p["kind"] == "resistor":
                p["fixed"] = True
    elif family == "mixer":
        parameter("brf", "bias", 0.65)
        parameter("blo", "bias", 0.85)
        stimulus += ["vrfp vrfp 0 DC {brf*vdd} SIN({brf*vdd} 12.5m 100Meg)",
                     "vrfn vrfn 0 DC {brf*vdd} SIN({brf*vdd} -12.5m 100Meg)",
                     "vlop vlop 0 DC {blo*vdd} SIN({blo*vdd} 50m 120Meg)",
                     "vlon vlon 0 DC {blo*vdd} SIN({blo*vdd} -50m 120Meg)"]
        rf = parameter("rfilter", "resistor", 1e3)
        cf = parameter("cfilter", "capacitor", 100e-15)
        lines += [f"rfp voutp vdd {rf}", f"rfn voutn vdd {rf}",
                  f"cfp voutp vdd {cf}", f"cfn voutn vdd {cf}"]
        output = "voutp"
    name = f"acp_p{task:02d}"
    directory = HERE / f"p{task:02d}_{label}"
    directory.mkdir(exist_ok=True)
    header = [f"* AnalogCoderPro task {task}: {label}", f"* Upstream {REVISION} / {path}",
              "* Native SPICE port; run using verification/run.py.",
              "* Connectivity preserved; GND normalized to 0; sizing/bias supplied per case.",
              '.include "model.inc"', '.include "parameters.inc"', '.temp 27']
    (directory / "testbench.cir").write_text("\n".join(header + stimulus + lines +
                                                  ['.include "analysis.inc"', '.end', '']))
    return dict(id=name, task=task, label=label, family=family, directory=directory.name,
                source=path, source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                differential=differential, output=output, nodes=sorted(nodes | {"vdd", output}),
                devices=devices, parameters=params)


def main():
    revision = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
    if revision != REVISION:
        raise SystemExit(f"Expected upstream revision {REVISION}, got {revision}")
    cases = [translate(task, *details) for task, details in TASKS.items()]
    (HERE / "catalog.json").write_text(json.dumps(dict(upstream="git@github.com:laiyao1/AnalogCoderPro.git",
        revision=REVISION, circuits=cases), indent=2) + "\n")
    print(f"Imported {len(cases)} transistor-level examples; upstream files were not executed.")


if __name__ == "__main__":
    main()
