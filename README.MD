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

Requires `ngspice` on your PATH and Python 3 with Matplotlib, NumPy, and SciPy.
Install Python dependencies with `python3 -m pip install -r verification/requirements.txt`.
From the repository root:

```sh
python3 verification/run.py                            # All 18 circuits, nominal supplies
python3 verification/run.py --model lp                 # All circuits on LP only
python3 verification/run.py inverter --model hp        # HP inverter only
python3 verification/run.py ring_oscillator --model lp # LP ring oscillator only
```

The runner creates the output directories, simulates without a GUI, checks the
exported waveforms, and saves PNG plots. It exits with a nonzero status on
simulation or verification failure. The default command verifies all 18 circuits
on both models at nominal supplies. Each run replaces only the selected combination's
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

## AnalogCoderPro performance benchmarks

The suite ports all 16 transistor-level samples (tasks **1–8 and 14–21**) from
[AnalogCoderPro](https://github.com/laiyao1/AnalogCoderPro/tree/05542af46020e5c37d5a7e3ca79da9f24626e1c9).
The local SSH clone at `AnalogCoderPro/` is pinned to that revision and ignored
by Git. The adapted SPICE circuits run independently of the clone and PySpice;
each testbench and the tracked catalog record the source path and revision.

The recorded reference run completed **24,576 candidate evaluations** and
**48/48 cases passed** full verification. Replaying the selected designs also
passed all 48 cases and regenerated **123 response PNGs plus two comparison PNGs**.

```sh
# Replay the selected designs and regenerate all 48 verification reports.
python3 verification/run.py analogcoderpro --supply both

# One task / model / supply condition.
python3 verification/run.py acp_p19 --model lp --supply common

# Repeat the independent sizing and bias search (longer-running).
python3 verification/run.py analogcoderpro --model all --supply both \
  --optimize --trials 512 --seed 42

# Explicitly replace tracked replay inputs with the verified new selections.
python3 verification/analogcoderpro/select_parameters.py
```

Normal verification uses the checked-in `parameters.json` files and performs
fresh simulations. Optimization writes ignored `best.json` and trial histories;
it does not automatically change tracked selections. `select_parameters.py`
checks the complete verified matrix before updating those inputs.

Each circuit has its own source directory under `verification/analogcoderpro/`:

```text
p01_common_source/             # Same layout for the other 15 tasks
  testbench.cir
  parameters.json              # Selected designs: tracked, reproducible inputs
  results/                     # All generated files below are Git-ignored
    hp/nominal/
    lp/nominal/
    lp/common_1v/
results/                       # Ignored aggregate reports and comparison PNGs
```

The nominal comparison uses HP at **1.0 V** and LP at **1.1 V**. The common-supply
comparison uses **1.0 V for both**, reusing the HP result. These are 48 unique
cases. Each case gets an independent search with identical parameter bounds;
the reported designs can have different dimensions and DC biases. External
loads, signal amplitudes, and frequencies stay fixed between models.

| Task selectors | Circuit examples |
| --- | --- |
| `acp_p01`–`acp_p05` | Common-source, three-stage, source-follower, common-gate, cascode amplifiers |
| `acp_p06`, `acp_p07` | Resistive-load and CMOS inverters |
| `acp_p08`, `acp_p17` | Current source and cascode current mirror |
| `acp_p14`, `acp_p15` | Miller-compensated and diode-load amplifiers |
| `acp_p16`, `acp_p18`, `acp_p20`, `acp_p21` | Active-load, resistive-load, two-stage, and telescopic differential amplifiers |
| `acp_p19` | Gilbert mixer |

Connectivity and equal-device groups follow the samples, including task 2's
actual stage connections. `GND` is normalized to SPICE ground. Original 5 V
supplies and level-1 models are replaced by the selected PTM card and supply.
Starting widths preserve the original W/L ratios at L=45 nm; the dimensionless
task-6 transistor gets an explicit initial W=450 nm. Internal capacitors and
mixer stimuli are retargeted for the PTM experiment. These are adaptations,
not reproductions of the upstream 5 V results.

The search uses seeded differential evolution with a hard 512-evaluation cap,
four isolated ngspice workers, and no polishing search. If the population
converges early, a separately seeded Sobol sequence completes the budget.
Widths span **90 nm–20 µm**, lengths **45–450 nm**, resistors **100 Ω–10 MΩ**,
internal capacitors **1 fF–10 pF**, and DC bias fractions **0.02–0.98 VDD**.
Paired devices retain shared parameters. Amplifiers and inverters have a fixed
**1 fF** external load.
Stored parameters use SI units (metres, ohms, farads); bias parameters are
fractions of VDD. The catalog identifies each parameter's kind and bounds.

| Family | Efficiency objective and verification floors |
| --- | --- |
| Amplifier | Maximize `A0 × f3dB / P`; gain ≥2 V/V (≥0.5 for follower), bandwidth ≥1 MHz, conducting devices, and valid output headroom. Differential examples also require CMRR ≥20 dB. |
| Inverter | Minimize `energy per transition × mean delay`; both rails within 5%, settled inversion, and positive delays below 250 ps with a 1 ns input period. |
| Current source / mirror | Maximize `1/[P × (tracking error + regulation + 0.001)]`; target 10 µA within 10%, current variation ≤20% over 0.5–0.9 VDD output voltage. |
| Mixer | Maximize differential down-conversion gain per watt; gain ≥0 dB and both mixing products ≥1 µV peak. LO inputs must remain within the rails. |

Amplifier AC sweeps cover 1 kHz–100 GHz. A response without a −3 dB crossing is
reported as a **bandwidth lower bound**, with the sweep limit used conservatively
in its objective. Differential AC input is 1 V and common-mode AC input is 0.5 V,
with gain normalization applied. Full verification compares the 1 MHz small-signal
transient gain against AC (within 10%) and also saves a DC transfer sweep.
The reported output swing is the full DC transfer range.

Inverter supply energy is average second-cycle VDD power divided by two
transitions per 1 ns period; timing thresholds are 50% of the selected supply.
Current-source compliance tests force the output voltage while retaining the
sample's load resistor as a fixture. Their power metric is `VDD × Iout`, plus
`VDD × 10 µA` for the mirror reference, so the forcing source cannot make a
current source appear to consume zero power.
Output resistance is the reciprocal fitted current-versus-voltage slope over
the 0.5–0.9 VDD regulation interval.

Mixer RF/LO frequencies are **100/120 MHz**, with **50/200 mV peak-to-peak
differential** inputs. Full verification runs 1.2 µs, uniformly resamples the
last 1 µs at 50 ps, and uses a Hann-window FFT to measure the **20/220 MHz**
products and RF/LO feedthrough. Search trials use a shorter coherent window;
the selected candidate is independently rerun with the full verification.

Each result directory contains a runnable `best.cir`, generated model/parameter/
analysis includes, the simulator log, raw data, `metrics.json`, `validation.txt`,
and applicable DC, AC, transient, or FFT PNGs. Optimization also saves all trial
parameters, metrics, constraint violations, and errors in `optimization.jsonl`.
The model and testbench hashes, ngspice version, revision, seed, and trial count
are recorded with the results.

Open the generated [comparison report](verification/analogcoderpro/results/comparison.md),
[CSV measurements and parameters](verification/analogcoderpro/results/comparison.csv),
[nominal-supply plot](verification/analogcoderpro/results/nominal.png), or
[common-1.0-V plot](verification/analogcoderpro/results/common_1v.png).
FoMs have different definitions between families and are compared within each
task only. A measured design that misses a floor is **LIMITED**, with the
violations recorded. **FAIL** denotes simulation or verification errors and
makes the runner exit nonzero. A LIMITED design is not a PASS; its efficiency
ratio is excluded from the aggregate performance chart.

To restore the optional upstream checkout for source inspection/imports:

```sh
git clone git@github.com:laiyao1/AnalogCoderPro.git AnalogCoderPro
git -C AnalogCoderPro checkout --detach 05542af46020e5c37d5a7e3ca79da9f24626e1c9
```

Results describe the best designs found within the search budget, not global
optima or foundry-characterized performance.
