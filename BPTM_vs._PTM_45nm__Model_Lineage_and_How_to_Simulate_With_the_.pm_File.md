# BPTM 45nm vs. PTM 45nm: What It Is and How to Simulate With the .pm File

"BPTM 45nm" is not a separate PDK. It is the Berkeley-era name for the same Predictive Technology Model project you found as "PTM 45nm." The model cards were first released at UC Berkeley as BPTM and are now distributed as PTM by Prof. Yu Cao's group, first at Arizona State University and now at the University of Minnesota.\[1\] What you downloaded is a BSIM4 (level 54) SPICE model card.\[2\] You use it by including the file in a netlist and instantiating MOSFETs that call the model names `nmos` and `pmos`.\[3\]

## TL;DR
- **BPTM and PTM are the same lineage.** PTM describes itself as "an evolution of previous Berkeley Predictive Technology Model (BPTM)."\[4\] A paper citing "BPTM 45nm" most likely used the early 45nm BSIM4 bulk card (V0.0, July 31, 2002) or the 2006 V1.0 `45nm_bulk.pm`. Most post-2008 papers use `45nm_HP.pm` (PTM HP v2.1, Vdd = 1.0 V) or `45nm_LP.pm` (Vdd = 1.1 V). Check the paper's Vdd and year to tell which.
- **A .pm file is not a PDK.** It contains only `.model nmos` / `.model pmos` BSIM4 parameter cards: no DRC/LVS, extraction, PCells, standard cells or corners. For a real 45nm academic kit, use NCSU FreePDK45 (whose HSPICE models are themselves based on 45nm PTM) together with the Nangate 45nm Open Cell Library.\[5\]
- **Usage in one line:** `.include 45nm_HP.pm` plus `M1 d g s b nmos W=90n L=45n`, with Vdd = 1.0 V.
  - HSPICE runs the file unmodified.
  - ngspice may warn about or remap the `version = 4.0` line. Change it to `version = 4.5` (or 4.8) if you hit problems.
  - LTspice accepts level 54 as BSIM4.
  - Spectre reads it as SPICE syntax if the file extension is not `.scs`. Set the analogLib nmos4/pmos4 model names to `nmos`/`pmos`.\[6\]

## Key Findings

### 1. What "BPTM 45nm" means and how it relates to PTM 45nm

**History and naming**
- BPTM (Berkeley Predictive Technology Model) came from the UC Berkeley Device Group (Chenming Hu's group). Yu Cao developed it there in the late 1990s.\[1\]
- The canonical BPTM citation is Y. Cao, T. Sato, M. Orshansky, D. Sylvester and C. Hu, "New paradigm of predictive MOSFET and interconnect modeling for early circuit simulation," *Proc. IEEE CICC*, pp. 201–204, 2000 (DOI 10.1109/CICC.2000.852648).\[7\]\[8\]\[9\]
- That first methodology generated BSIM3v3 cards. Designers could enter L_eff, T_ox, V_t, R_dsw and interconnect dimensions to "instantly obtain a BSIM3v3 customized model."\[10\]
- Older papers cite the Berkeley URL `http://www-device.eecs.berkeley.edu/~ptm/`. \[11\] That site is gone.

**The "new generation" PTM**
- Cao moved to ASU, where the Nanoscale Integration and Modeling (NIMO) group rebuilt the methodology as the "new generation" PTM.\[12\]
- Canonical citations:
  - W. Zhao and Y. Cao, "New generation of predictive technology model for sub-45 nm early design exploration," *IEEE Trans. Electron Devices*, vol. 53, no. 11, pp. 2816–2823, Nov. 2006 (DOI 10.1109/TED.2006.884077).\[9\]\[13\]\[14\]
  - The ISQED 2006 conference version (DOI 10.1109/ISQED.2006.91).\[15\]\[16\]
  - The ACM JETC 2007 paper "Predictive technology model for nano-CMOS design exploration."\[17\]\[18\]\[19\]
- Cao's 2011 Springer book on PTM explains why the reboot happened. It says BPTM "provides reasonable models for technology nodes from 180 to 45 nm," but its "empirical nature constrains the physicality and scalability of the predictions." It also says the old approach missed parameter correlations that "could cause significant underestimation of performance variability."\[1\]
- The practical consequence: a "BPTM 45nm" card and a 2008 "PTM HP 45nm" card are different parameter sets. Do not expect them to give identical numbers.

**Release history of the 45nm files**

| Date | Release | Likely filename / description | Who cites it |
|---|---|---|---|
| Jul 31, 2002 | 45nm BSIM4 model card for bulk CMOS, V0.0 | Berkeley/BPTM-era card | Papers citing "BPTM 45nm," roughly 2002–2006 |
| Feb 22, 2006 | New-generation PTM bulk CMOS, 130–32nm, V1.0 | `45nm_bulk.pm` (2006 directory) | Many 2006–2009 papers; used to characterize the Nangate 45nm Open Cell Library |
| Oct 2007 | 45nm PTM for metal gate/high-k CMOS, V2.0 | `45nm_MGK.pm` | Papers mentioning gate-leakage, temperature or body-bias features |
| Sep 30, 2008 | PTM HP (high-k/metal gate + strain), V2.1 | `45nm_HP.pm`, Vdd = 1.0 V | The default "PTM 45nm" in most post-2008 papers\[20\] |
| Nov 15, 2008 | PTM LP (low power), V2.1 | `45nm_LP.pm`, Vdd = 1.1 V | Low-leakage / low-power papers |
| Jun 1, 2012 | PTM-MG (BSIM-CMG FinFETs), 20–7nm, HP and LSTP | Not 45nm | Not relevant to 45nm\[20\] |

There was also a 45nm FinFET sub-circuit model (V0.0, Sep 30, 2005).\[20\] It is rarely what people mean by "45nm."

**How to tell which file a paper used**
- **Vdd 1.0 V and "high-k/metal gate/strained-Si"** → `45nm_HP.pm`.
- **Vdd 1.1 V** → `45nm_LP.pm`.
- **Paper from before 2006 that says "BPTM"** → the 2002 V0.0 bulk card.
- **2006–2008 paper citing "45nm BSIM4 model card for bulk CMOS"** → the 2006 `45nm_bulk.pm`.

If the paper doesn't say, the HP card is the safest default today, and you should state which file you used.

**Where to download.** The historical site is ptm.asu.edu (earlier `www.eas.asu.edu/~ptm`). \[17\] The project now has a home at the University of Minnesota, `mec.umn.edu/ptm`, where Cao is the Louis John Schnell Professor and runs the Microelectronics Co-design group.\[21\] That page lists the same four canonical references.\[7\]\[22\] Several forum users have reported ptm.asu.edu as unreachable at times.\[23\] If so, use the UMN page; course mirrors are a fallback.

### 2. A .pm file is not a PDK

**What the file is.** It contains two `.model` statements (BSIM4 parameter cards) and nothing else:
- no layout layers or design rules
- no DRC/LVS/PEX decks
- no PCells or standard cells
- no models for resistors, capacitors or diodes
- no corner or Monte Carlo sections

A SemiWiki answer puts it well: "the PTM model file is a list of BSIM4 parameters that describes the transistor of a particular technology generation."\[2\]

**If you need a real (predictive) 45nm kit, use FreePDK45:**
- **Origin:** NCSU (with Oklahoma State). It is a generic, open-source PDK that "does not correspond to any real process and cannot be fabricated."\[24\]\[25\]
- **Release 1.4 (2011-04-07)** includes:
  - Calibre DRC, LVS and xRC rules\[5\]
  - Virtuoso technology files
  - VTL/VTG/VTH/THKOX device flavors
  - HSPICE models in nominal, fast and slow variants, "based on 45nm PTM." The 1.4 notes say these were "significantly re-worked to more closely match commercial technologies."\[5\]
- **Nangate 45nm Open Cell Library:** built on FreePDK45 and characterized with PTM. Its README names "The 45nm BSIM4 model card for bulk CMOS V1.0 from ASU released 2006-02-22." According to the Si2 OpenEDA project page, its first release had "38 different functions ranging from buffers to scan flip-flops with set and reset," in more than 100 cells.
- **Adoption:** Joseph Davis's April 14, 2015 post on the Siemens "Design with Calibre" blog counted "over 200 published citations for the freePDK45 and over 1000 for the associated Nangate 45nm Open Cell Library."
- **Packaging:** mflowgen and OpenROAD flows package the two together as "NanGate45."\[24\]\[26\]

**If you don't need 45nm specifically,** the open-source SkyWater SKY130 and GF180MCU PDKs come with real foundry models, corners and full DRC/LVS. They run in ngspice and Xyce, and you can actually tape out with them, but they are 130nm and 180nm.

## Details

### 3. What's inside `45nm_HP.pm`

These lines are verbatim from the PTM HP v2.1 card (the copy in the VTR project's `PTM_45nm` directory):

```
* PTM High Performance 45nm Metal Gate / High-K / Strained-Si
* nominal Vdd = 1.0V
.model nmos nmos level = 54
+version = 4.0 binunit = 1 paramchk= 1 mobmod = 0
+tnom = 27 toxe = 1.25e-009 toxp = 1e-009 toxm = 1.25e-009
+dtox = 2.5e-010 epsrox = 3.9 wint = 5e-009 lint = 3.75e-009
+xl = -20e-9
+vth0 = 0.46893 k1 = 0.4 k2 = 0 k3 = 0
...
.model pmos pmos level = 54
+version = 4.0 ...
+tnom = 27 toxe = 1.3e-009 ...
+vth0 = -0.49158 ...
```

| Parameter | NMOS | PMOS | Meaning |
|---|---|---|---|
| level / version | 54 / 4.0 | 54 / 4.0 | BSIM4 (HSPICE level 54), BSIM4.0 parameter set |
| toxe | 1.25 nm | 1.3 nm | Electrical equivalent oxide thickness, in metres |
| vth0 | 0.469 V | −0.492 V | Long-channel zero-bias threshold voltage |
| u0 | 0.054 | 0.02 | Low-field mobility, in m²/V·s |
| lint / xl | 3.75 nm / −20 nm | 3.75 nm / −20 nm | Length offsets: the effective channel is much shorter than the drawn L |
| tnom | 27 °C | 27 °C | Temperature at which the parameters were extracted |

**Units and scaling.** Everything is in SI units, with no `scale` option. Write `L=45n W=90n`, not `L=45 W=90`.

**Drawn vs. effective length.** Because of `xl` and `lint`, a drawn L = 45 nm gives a much shorter effective channel. By my own BSIM4 arithmetic (L + XL − 2·LINT), that is about 17.5 nm. This matches PTM's practice of quoting the node name as the drawn length.

**Typical sizing.** IIT Madras lists the 45nm HP model as "V_dd=1V, W_min=90nm, L_min=45nm."\[27\] Use these as your default minimum device. The LP card uses the same model names with a 1.1 V nominal supply.\[28\]

**Not verified here.** I could not check the full parameter values of the 2006 `45nm_bulk.pm` or the 2002 BPTM card against a primary copy. PTM-generator outputs derived from the 2006 defaults show NMOS toxe = 1.75 nm and vth0 ≈ 0.47 V.\[29\] If your paper used that file, compare your copy's header against it.

### 4. Using the file in each simulator

#### 4a. HSPICE (runs the file unmodified)
```spice
* nmos_idvg.sp  -- PTM 45nm HP NMOS characterization
.include '45nm_HP.pm'          $ file has no .lib sections, so use .include
.option post
.temp 27
.param vdd=1.0
Vd d 0 'vdd'
Vg g 0 'vdd'
M1 d g 0 0 nmos W=90n L=45n    $ D G S B  model-name  (model names are 'nmos'/'pmos')
.dc Vg 0 'vdd' 0.01 sweep Vd poi 2 0.05 'vdd'
.print dc I(Vd)
.end
```
- HSPICE implements UC Berkeley BSIM4 as LEVEL 54, so `version = 4.0` is accepted directly.\[30\]\[31\]
- **Only use `.lib 'file' TT` if you wrap the cards yourself** in `.lib TT … .endl TT`. The stock file has no sections.

#### 4b. ngspice (most common source of trouble)
- ngspice supports BSIM4 as levels 14 and 54.\[32\] **It picks the BSIM4 code version from the `version` keyword.**\[33\]
- **What `version = 4.0` triggers:**
  - Current ngspice routes versions 4.0 to 4.5 to its BSIM4v5 implementation (the 4.6, 4.7 and 4.8 families get their own code).\[33\]
  - Some builds print warnings such as *"This model supports BSIM4.2.1, 4.3.0 and 4.4.0; you specified a wrong version number."*\[34\]
  - Very old builds (ngspice-18) rejected 4.0 outright.\[35\]\[36\]
- **The ngspice manual recommends newer versions:** "We recommend that you use only the most recent BSIM4 model (version 4.8.1) … change the version parameter in your modelcard files to VERSION = 4.8." With no version given, the newest is selected.\[32\]
- **Practical fix:** edit both `.model` lines to `+version = 4.5` (as the UP Diliman ngspice tutorial did for the 45nm LP card)\[12\] or to `4.8`. Keep a note in your report that you changed it.
- **Expect small numeric differences** between versions. Keep the version fixed across all your runs.

```spice
* inv_vtc_tran.cir -- ngspice
.include 45nm_HP.pm             ; after editing version=4.0 -> 4.5 (or 4.8)
.param vdd=1.0
Vdd vdd 0 {vdd}
Vin in 0 PULSE(0 {vdd} 100p 20p 20p 480p 1n)
Mp out in vdd vdd pmos W=180n L=45n
Mn out in 0   0   nmos W=90n  L=45n
Cl out 0 1f
.control
  dc Vin 0 1.0 0.005
  plot v(out)                   ; VTC
  tran 1p 2n
  meas tran tphl TRIG v(in) VAL=0.5 RISE=1 TARG v(out) VAL=0.5 FALL=1
  meas tran tplh TRIG v(in) VAL=0.5 FALL=1 TARG v(out) VAL=0.5 RISE=1
  plot v(in) v(out)
.endc
.end
```

**Other ngspice problems and fixes:**
- **Unknown or ignored parameters:** remove them, or upgrade ngspice. Old builds lacked some 4.7/4.8 parameters.
- **"could not find a valid modelname":** the instance's model name doesn't match the `.model` name, or the include path is wrong.
- **Compatibility settings:** put `set ngbehavior=hs` in `.spiceinit` if you also reuse HSPICE-style netlists.

You can probe device quantities directly, for example `print @mn[vth] @mn[gm] @mn[gds]`. The UP Diliman tutorial reports Vth ≈ 0.56 V for the LP NMOS this way.\[12\]

#### 4c. LTspice
1. Put `45nm_HP.pm` next to your `.asc` file.
2. Add a SPICE directive: `.include 45nm_HP.pm`.
3. Use the 4-terminal `nmos4`/`pmos4` symbols, set their Value to `nmos`/`pmos`, and set `L=45n W=90n`.

LTspice maps level 54 (and 14) to BSIM4. An LTspice user-group veteran warns that "what we can't tell … is how complete that support is."\[37\] Treat LTspice as fine for teaching-level DC and transient work. Cross-check anything publishable (leakage, gate tunneling, noise) in HSPICE, ngspice or Spectre.

#### 4d. Cadence Virtuoso / Spectre
1. **Keep a non-`.scs` extension.** Cadence's Andrew Beckett: "if the suffix is '.scs' it is assumed to be in spectre language, whereas any other suffix is assumed to be in SPICE language. Your models are in SPICE language, so pick anything other than '.scs'."\[6\]
   - If you must use `.scs`, or you're wrapping the file, put `simulator lang=spice` at the top. Add `simulator lang=spectre` after the cards if Spectre code follows.\[38\]\[39\]
2. In ADE: **Setup → Model Libraries**, add the path to `45nm_HP.pm`, and leave Section blank (the file has none).\[40\]
3. Place **analogLib `nmos4`/`pmos4`** and set the **Model name** to `nmos` and `pmos`, "whatever word is after the .model in the file." Connect the body terminals explicitly.\[6\]\[38\]
4. If you want Spectre-native netlists, a minimal text deck is:
   ```
   simulator lang=spice
   .include "45nm_HP.pm"
   simulator lang=spectre
   M1 (d g 0 0) nmos w=90n l=45n
   ```
5. Use `spectre -h bsim4` to look up any parameter's meaning.\[6\]

Older IC5 setups with spectreS or cdsSpice sometimes choked on BSIM4.\[41\] Use plain Spectre (or APS).

#### 4e. Xyce (free, HSPICE-like)
- Xyce supports BSIM4 as level 14/54. Since release 7.6 it selects among **4.6.1, 4.7.0 and 4.8.2** with the VERSION parameter; earlier releases ignored VERSION and always used 4.6.1.\[42\]
- Set `version=4.8.2` (or 4.6.1) in the card, and run with `Xyce -hspice-ext all` for HSPICE syntax.\[43\]
- Sandia's own MOS-AK 2022 compatibility slide lists "PTM 45nm ✓."\[43\]

### 5. Verification circuits

Run these in order. If all three behave, your setup is sound.

1. **Id–Vgs / Id–Vds (HSPICE or ngspice, as above):**
   - Sweep Vgs 0→1 V at Vds = 0.05 V and 1.0 V, and plot on a log scale to see subthreshold slope and DIBL.
   - Then sweep Vds 0→1 V at several Vgs values.
   - For an NMOS with W = 90 nm you should see on-current in the tens of µA.
   - The GitHub repository junseok-oh-ee/ptm45-nmos-reproducible-analysis (ngspice + Python, Vth defined at I_D = 10⁻⁷ × W/L A) extracted an HP Vth of 0.324 V at Vds = 0.05 V and 0.185 V at Vds = 1.0 V, giving HP DIBL of 146 mV/V; it found about 0.53 V Vth and 77 mV/V DIBL for LP. Your numbers should land nearby.
2. **Inverter VTC and delay:**
   - Use the ngspice deck above: Wp/Wn = 2 (180n/90n), Vdd = 1.0 V.
   - Check that the switching threshold is near Vdd/2 and that rail-to-rail output is reached.
   - Measure tpHL/tpLH with a 1 fF load; expect picoseconds to tens of picoseconds.
3. **Ring oscillator (ngspice/HSPICE):**
```spice
* ro11.cir  -- 11-stage ring oscillator, PTM 45nm HP
.include 45nm_HP.pm
.param vdd=1.0
.subckt inv in out vdd
Mp out in vdd vdd pmos W=180n L=45n
Mn out in 0   0   nmos W=90n  L=45n
.ends
Vdd vdd 0 {vdd}
X1 n1 n2 vdd inv
X2 n2 n3 vdd inv
X3 n3 n4 vdd inv
X4 n4 n5 vdd inv
X5 n5 n6 vdd inv
X6 n6 n7 vdd inv
X7 n7 n8 vdd inv
X8 n8 n9 vdd inv
X9 n9 n10 vdd inv
X10 n10 n11 vdd inv
X11 n11 n1 vdd inv
.ic v(n1)=0                    ; kick-start the ring
.tran 1p 2n uic
.control
  run
  meas tran tper TRIG v(n1) VAL=0.5 RISE=2 TARG v(n1) VAL=0.5 RISE=3
  let f = 1/tper
  let tpd = tper/(2*11)        ; per-stage delay
  print f tpd
.endc
.end
```
   - f = 1/(2·N·t_pd).\[44\]\[45\] Use the per-stage delay to sanity-check against the inverter test.
   - In HSPICE, replace the `.control` block with `.measure tran` statements.

### 6. Common pitfalls

- **Model-name mismatch.** The cards are literally named `nmos` and `pmos`.
  - In some simulators these collide with built-in type keywords or with other libraries' names. If you include two PTM files (for example HP and LP) at once, rename them, e.g. `.model nmos_hp nmos level=54`.
  - Some redistributions rename them (for example `PTMHP45N`, or FreePDK45's `NMOS_VTL`).\[28\]\[46\]\[47\]\[48\] Always grep the file for `.model`.
- **Bulk terminal.** Tie the NMOS body to ground and the PMOS body to Vdd, unless you are studying body bias. A floating or self-connected bulk changes Vth through the body effect.
- **Units and minimum sizes.**
  - Write `n`, not plain numbers. `W=90` means 90 metres.
  - Stay at L ≥ 45 nm and W ≥ 90 nm for HP. Below the drawn node length the card leaves its fitted range.
  - The cards have no binning; `binunit=1` with no bins means one global parameter set.
- **Temperature.** The parameters are extracted at `tnom = 27` °C. Set `.temp`/`.option temp=` explicitly and sweep it (for example −40/27/125 °C) if temperature matters. The HP/LP v2.x and MGK cards were released with "temperature effect" modeling,\[4\] while the 2002 BPTM card is cruder.\[20\]
- **No process corners.** The stock cards are typical-typical only. Options:
  - **(a)** Use PTM's online "Nano-CMOS" generator. An EDAboard moderator notes it can output level-54 files "at least for TT, SS and FF."\[49\] You can transfer the same percentage shifts to LP or HP cards.\[49\]
  - **(b)** Build corners yourself by shifting `vth0` (for example ±10% or ±30–50 mV) and `toxe` (±5–10%), plus optionally `u0`. Use FS/SF skews for NMOS vs. PMOS.
  - **(c)** Use FreePDK45's fast/slow HSPICE models.\[5\]
  - State your assumptions. An Auburn University thesis on the energy efficiency and process-variation tolerance of 45nm bulk and high-k circuits cites earlier work finding that "controlling the process variation parameters to ±10% yielded a threshold voltage variation of ±15%."
- **Monte Carlo.** PTM ships no statistical or mismatch file, as commenters on the Analog Integrated Circuit Design site point out.\[23\]
  - Make `vth0`, `toxe` and `u0` parameters, e.g. `vth0='0.46893+dvthn'`.
  - In HSPICE, use `.param dvthn=agauss(0,0.015,1)` with `.tran … sweep monte=200`.
  - In ngspice, use `.control` loops with `sgauss()` and `altermod`.
  - For local mismatch, scale σ with Pelgrom's law (σVth ∝ 1/√(WL)).
- **Version mix-ups.**
  - Some GitHub copies named `45nm_bulk.pm` actually contain the HP v2.1 header.\[50\] Always read the first two comment lines (`* PTM High Performance …`, `* nominal Vdd = …`).
  - Mixing a BSIM4.0-era card with a 4.8 engine changes results slightly. Report simulator, version and file.
- **Accuracy expectations.** The paper "Evaluation of predictive technology models" (*Microelectronics Journal*, vol. 80, Oct. 2018, pp. 7–17) counted over 390 IEEE Xplore papers citing ASU PTM. It found "the high-performance ASU PTM 2.1 models show good correlation to published commercial planar high-k metal gate data at the 45 and 32 nm nodes." PTM is a credible stand-in, but it is still a prediction, not a foundry model.

## Recommendations

1. **To reproduce a paper that says "BPTM 45nm":**
   - Find its stated Vdd, Tox or Vth and publication year to identify the file (table in §1).
   - If it's ambiguous, use `45nm_HP.pm` at 1.0 V and say so explicitly. Don't expect exact numerical matches with pre-2006 BPTM results.
2. **For circuit-level work (inverters, SRAM, comparators, ring oscillators):**
   - Use the PTM 45nm HP or LP card with ngspice (free) or HSPICE/Spectre (if licensed).
   - Change `version` to 4.5 or 4.8 for ngspice.
   - Run the three verification decks above before anything else.
3. **For layout, post-layout parasitics, standard-cell synthesis or place-and-route:** switch to FreePDK45 + Nangate45. Its transistor models are PTM-derived, so your schematic-level results stay comparable.
4. **For silicon-realistic analog work with corners and mismatch:** consider SKY130 or GF180 instead. You give up the 45nm label but gain real foundry statistics.
5. **Always report** the exact file (name plus header), simulator and version, the BSIM4 `version` value you used, temperature, and how you built any corners or Monte Carlo.

## Caveats

- ptm.asu.edu blocks automated access and has been intermittently unreachable. The release dates and file descriptions above come from its "Latest models" and "Introduction" pages via search snippets and from mirrors. The UMN page (mec.umn.edu/ptm) is the current home.\[7\]
- The verbatim HP v2.1 parameters were checked against a widely used GitHub mirror (VTR), not directly against the ASU server.
- I could not obtain the full original 2002 BPTM 45nm card or the full 2006 `45nm_bulk.pm` for verification. The values quoted for the 2006-style card come from PTM-generator outputs.
- The ~17.5 nm effective-length figure is my own derivation from BSIM4's L_eff formula, not a PTM-published number.
- ngspice's handling of `version = 4.0` has changed across releases (rejected in ngspice-18, remapped later, routed to BSIM4v5 today).\[35\] Check your build's warnings.
- LTspice's BSIM4 completeness is undocumented.

## Sources

1. [Predictive Technology Model for Robust Nanoelectronic Design - PDF Free Download](https://epdf.pub/predictive-technology-model-for-robust-nanoelectronic-design.html)
2. [How to know,calculate the Cox,mobility values from model files](https://semiwiki.com/forum/threads/how-to-know-calculate-the-cox-mobility-values-from-model-files.2362/)
3. [GitHub - zlakio/lector-leakage-45nm: Implementing and improving the LECTOR leakage-reduction technique for a CMOS inverter, · GitHub](https://github.com/zlakio/lector-leakage-45nm)
4. [PTM - Introduction](http://ptm.asu.edu/introduction.html)
5. [www.eda.ncsu.edu](https://www.eda.ncsu.edu/freepdk/freepdk45/)
6. [include a model files for nmos and pmos into virtuoso - Custom IC Design - Cadence Technology Forums - Cadence Community](https://community.cadence.com/cadence_technology_forums/f/custom-ic-design/30083/include-a-model-files-for-nmos-and-pmos-into-virtuoso)
7. [PTM - University of Minnesota](https://mec.umn.edu/ptm)
8. [The Predictive Technology Model in the Late Silicon Era and Beyond](https://dl.acm.org/doi/10.1561/1000000012)
9. [Predictive Technology Model of Conventional CMOS Devices](https://link.springer.com/chapter/10.1007/978-1-4614-0445-3_2)
10. [(PDF) New paradigm of predictive MOSFET and interconnect modeling for early circuit simulation](https://www.researchgate.net/publication/3852795_New_paradigm_of_predictive_MOSFET_and_interconnect_modeling_for_early_circuit_simulation)
11. [Simulation study of CMOS based 6 Transistors SRAM](https://ijettjournal.org/archive/ijett-v44p243)
12. [Tutorial: Using ngspice | Microelectronics and Microprocessors Laboratory](https://www.up-microlab.org/resources/tutorials/tutorial-using-ngspice/)
13. [New generation of predictive technology model for sub-45 nm early design exploration - Experts@Minnesota](https://experts.umn.edu/en/publications/new-generation-of-predictive-technology-model-for-sub-45-nm-early/)
14. [New Generation of Predictive Technology Model for Sub-45 nm Early Design Exploration](https://www.researchgate.net/publication/3075141_New_Generation_of_Predictive_Technology_Model_for_Sub-45_nm_Early_Design_Exploration)
15. [New generation of predictive technology model for sub-45nm design exploration](https://www.researchgate.net/publication/4232956_New_generation_of_predictive_technology_model_for_sub-45nm_design_exploration)
16. [New Generation of Predictive Technology Model for Sub-45nm Design Exploration](https://dl.acm.org/doi/10.1109/ISQED.2006.91)
17. [Predictive technology model for nano-CMOS design exploration - Experts@Minnesota](https://experts.umn.edu/en/publications/predictive-technology-model-for-nano-cmos-design-exploration/)
18. [Predictive Technology Model for Nano-CMOS Design Exploration](https://www.researchgate.net/publication/220365585_Predictive_Technology_Model_for_Nano-CMOS_Design_Exploration)
19. [Evaluation of predictive technology models - ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0026269218302064)
20. [PTM - Latest models](http://ptm.asu.edu/latest.html)
21. [GitHub - junseok-oh-ee/ptm45-nmos-reproducible-analysis: Reproducible PTM 45 nm HP/LP NMOS analysis using ngspice and Python · GitHub](https://github.com/junseok-oh-ee/ptm45-nmos-reproducible-analysis)
22. [Yu Cao on alphaXiv](https://www.alphaxiv.org/@yu-cao)
23. [Model Files](https://analogicdesign.com/students/netlists-models/model-files/)
24. [GitHub - mflowgen/freepdk-45nm: ASIC Design Kit for FreePDK45 + Nangate for use with mflowgen · GitHub](https://github.com/mflowgen/freepdk-45nm)
25. [(PDF) FreePDK15TFET: An Open-source Process Design Kit for 15nm CMOS and TFET devices](https://www.researchgate.net/publication/351743473_FreePDK15TFET_An_Open-source_Process_Design_Kit_for_15nm_CMOS_and_TFET_devices)
26. [NanGate45 (FreePDK45, 45nm Open Cell Library, bsg\_fakeram memory generation)](https://tilos-ai-institute.github.io/MacroPlacement/Enablements/NanGate45/)
27. [CAD tools/libraries - Nagendra Krishnapura - IIT Madras](https://www.ee.iitm.ac.in/~nagendra/cadinfo.html)
28. [EEcircuit/models.md at gen1 · eelab-dev/EEcircuit · GitHub](https://github.com/danchitnis/EEsim/blob/main/models.md)
29. [ee220/src/45nm\_NMOS\_bulk69327.pm at master · louisalarcon/ee220 · GitHub](https://github.com/louisalarcon/ee220/blob/master/src/45nm_NMOS_bulk69327.pm)
30. [LEVEL 54 BSIM4.0 Model](http://www.ece.uci.edu/docs/hspice/hspice_2001_2-173.html)
31. [suggestion needed for BSIM4 in hspice](https://www.edaboard.com/threads/suggestion-needed-for-bsim4-in-hspice.142424/)
32. [BSIM4 model (levels 14, 54) -](https://nmg.gitlab.io/ngspice-manual/mosfets/mosfetmodels_nmos_pmos/bsim4model_levels14,54.html)
33. [fix(core): BSIM4 VERSION=4.3.0 rejected (corpus-f gain\_stage.cir); ngspice-47 runs · Issue #1218 · spicets/spice-ts · GitHub](https://github.com/spicets/spice-ts/issues/1218)
34. [ngspice / Discussion / ngspice-users: Regarding CMOS technology files](https://sourceforge.net/p/ngspice/discussion/133842/thread/b2e0d8cf/)
35. [ngspice / Discussion / ngspice-users: BSIM4 Support in NG-SPICE-REWORK-18](https://sourceforge.net/p/ngspice/discussion/133842/thread/11bd86ea/)
36. [\[Ngspice-devel\] bug or difference?](https://sourceforge.net/p/ngspice/mailman/message/22172729/)
37. [LTspice@groups.io](https://groups.io/g/LTspice/topic/level_54_in_ltspice/73373227)
38. [Implementation of the ZVN2106G Spice Model in Cadence Spectre](https://www.edaboard.com/threads/implementation-of-the-zvn2106g-spice-model-in-cadence-spectre.221689/)
39. [How to transfer spice model to spectre model - Custom IC Design - Cadence Technology Forums - Cadence Community](https://community.cadence.com/cadence_technology_forums/f/custom-ic-design/14736/how-to-transfer-spice-model-to-spectre-model)
40. [How to make a simulation on Cadence using .mod files?](https://www.edaboard.com/threads/how-to-make-a-simulation-on-cadence-using-mod-files.52756/)
41. [PTM MOSFET model files in cadence simulator](https://www.edaboard.com/threads/ptm-mosfet-model-files-in-cadence-simulator.148989/)
42. [Xyce™ Parallel Electronic Simulator Version 7.6 Release Notes](https://xyce.sandia.gov/files/xyce/Release_Notes_7.6.pdf)
43. [Xyce and support for modern PDKs Eric Keiter Sandia National Laboratories](https://www.mos-ak.org/silicon_valley_2022/presentations/Keiter_Xyce_AWG_MOS-AK_Dec_7_2022.pdf)
44. [Phase locked looped based digital pulse converter](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/6801028)
45. [Ring oscillator](https://en.wikipedia.org/wiki/Ring_oscillator)
46. [FreePDK45 model files](https://www.edaboard.com/threads/freepdk45-model-files.293135/)
47. [EEcircuit/models.md at gen1 · eelab-dev/EEcircuit · GitHub](https://github.com/eelab-dev/EEcircuit/blob/gen1/models.md)
48. [Calculating Propagation delay](https://www.edaboard.com/threads/calculating-propagation-delay.326668/)
49. [Predictive Technology Model (PTM) and process corners](https://www.edaboard.com/threads/predictive-technology-model-ptm-and-process-corners.202213/)
50. [GitHub - Tanvir-Mahmud-Mahim/Physics-Guided-Graph-RL-with-an-Adaptive-Fuzzy-Reward-for-Transferable-Analog-Transistor-Sizing · GitHub](https://github.com/Tanvir-Mahmud-Mahim/Physics-Guided-Graph-RL-with-an-Adaptive-Fuzzy-Reward-for-Transferable-Analog-Transistor-Sizing)
