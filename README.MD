# PTM 45nm models with ngspice

Both downloaded model cards have tested ngspice adaptations:

| Device | Include file | Nominal supply |
| --- | --- | ---: |
| High performance (HP) | [45nm_HP_ngspice.pm](45nm_HP_ngspice.pm) | 1.0 V |
| Low power (LP) | [45nm_LP_ngspice.pm](45nm_LP_ngspice.pm) | 1.1 V |

The inverter and 11-stage ring oscillator from the
[model-lineage document](BPTM_vs._PTM_45nm__Model_Lineage_and_How_to_Simulate_With_the_.pm_File.md)
were verified on **both models** with **ngspice 45.2** at **27 °C**.

## Run the examples

Requires `ngspice` on your PATH, Python 3, and Matplotlib. If Matplotlib is
missing, install it with `python3 -m pip install -r verification/requirements.txt`.
From the repository root:

```sh
python3 verification/run.py                            # Both circuits on HP and LP
python3 verification/run.py --model lp                 # Both circuits on LP only
python3 verification/run.py inverter --model hp        # HP inverter only
python3 verification/run.py ring_oscillator --model lp # LP ring oscillator only
```

The runner creates the output directories, simulates without a GUI, checks the
exported waveforms, and saves PNG plots. It exits with a nonzero status on
simulation or verification failure. The default command runs all four
circuit/model combinations. Each run replaces only the selected combination's
generated outputs and regenerates `validation.txt`.

All SPICE testbenches are organized under `verification/`:

```text
verification/
  run.py
  requirements.txt
  inverter/
    inv_vtc_tran.cir
    results/hp/          # Generated; ignored by Git
    results/lp/          # Generated; ignored by Git
  ring_oscillator/
    ro11.cir
    results/hp/          # Generated; ignored by Git
    results/lp/          # Generated; ignored by Git
```

| Testbench | Model | Generated PNG plots |
| --- | --- | --- |
| [Inverter](verification/inverter/inv_vtc_tran.cir) | HP | [DC transfer](verification/inverter/results/hp/vtc.png), [transient](verification/inverter/results/hp/tran.png) |
| Inverter | LP | [DC transfer](verification/inverter/results/lp/vtc.png), [transient](verification/inverter/results/lp/tran.png) |
| [11-stage ring](verification/ring_oscillator/ro11.cir) | HP | [Output transient](verification/ring_oscillator/results/hp/tran.png) |
| 11-stage ring | LP | [Output transient](verification/ring_oscillator/results/lp/tran.png) |

Each model's result folder also contains the example's `.log`, waveform `.dat`
files, `bsim4.out` diagnostics, `validation.txt`, and a generated `model.inc`
selecting exactly one model and its supply. PNG links become available after
running the examples. All generated artifacts are ignored by Git.

For direct ngspice use after the runner creates `model.inc`, change into the
desired result directory (for example `verification/inverter/results/lp/`)
and run `ngspice -n -b -o inverter.log ../../inv_vtc_tran.cir`. For the ring,
use its result directory and `ngspice -n -b -o ring_oscillator.log ../../ro11.cir`.
The Python runner also regenerates waveform validation and PNGs.

## Use the model in your circuit

Put the model beside your netlist and include it with `.include`:

```spice
.include "45nm_HP_ngspice.pm"
.temp 27
* MOSFET terminal order: drain gate source bulk model
Mn out in 0   0   nmos W=90n  L=45n
Mp out in vdd vdd pmos W=180n L=45n
```

For HP, provide a 1.0 V supply at `vdd` and an input source at `in`. For LP,
include `45nm_LP_ngspice.pm` instead and use a 1.1 V supply. Tie the NMOS bulk
to ground and the PMOS bulk to VDD. Use explicit unit suffixes: `45n` means
45 nm; `45` means 45 metres. Adjust the include path to the model's location.
The shared verification testbenches obtain the model and supply from the
runner's generated `model.inc`.
The model names are **`nmos`** and **`pmos`**. Include one model card per circuit;
HP and LP define the same model names.

## Verified results

| Measurement | HP (1.0 V) | LP (1.1 V) |
| --- | ---: | ---: |
| Output at input = 0 V | 0.999996 V | 1.100000 V |
| Output at input = VDD | 2.223 µV | 0.05254 µV |
| Switching voltage, input = output | 0.491163 V | 0.558015 V |
| High-to-low delay, `tphl` | 10.408 ps | 24.986 ps |
| Low-to-high delay, `tplh` | 8.873 ps | 21.390 ps |
| Ring oscillator period | 94.869 ps | 335.808 ps |
| Ring oscillator frequency | 10.541 GHz | 2.978 GHz |
| Ring oscillator per-stage delay | 4.312 ps | 15.264 ps |

Both examples use W/L = 90/45 nm for NMOS and 180/45 nm for PMOS. The inverter
has a **1 fF** load and sweeps 0 to VDD in 5 mV steps, then runs two pulse cycles
over 2 ns. Checks cover monotonic DC behavior, both output rails, inversion,
and delays at **50% of VDD** (0.5 V for HP, 0.55 V for LP).
The ring drives each following stage without extra load capacitors and runs
for 10 ns using initial conditions to start oscillation. Its period is measured
after 1 ns; checks cover sustained full-swing cycles, period stability, and
`frequency = 1/period`, `stage delay = period/(2*11)`. Both examples compare
ngspice measurements with independently interpolated waveform crossings.

## Model adaptation

The downloaded `45nm_HP.pm` and `45nm_LP.pm` are preserved. Each tested copy
(`45nm_HP_ngspice.pm` and `45nm_LP_ngspice.pm`) adds a provenance comment and
changes both NMOS and PMOS BSIM4 version selectors from **4.0 to 4.8**, following the
[ngspice manual](https://nmg.gitlab.io/ngspice-manual/mosfets/mosfetmodels_nmos_pmos/bsim4model_levels14,54.html).
All other model parameters are unchanged. Selecting a newer BSIM4 implementation
can change numerical results.

The run reports `Ngate = 1e+17 is less than 1.E18cm^-3` for each transistor model
in each analysis. This comes from the original card's `ngate=1e23` in SI units;
the value is retained. Both examples completed without parsing, convergence,
or measurement errors.

These are predictive transistor models, without process-corner or mismatch
libraries. HP and LP results above use each model's nominal supply.
