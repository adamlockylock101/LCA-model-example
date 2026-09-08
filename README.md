# Anti-leak film LCA model

A pluggable cradle-to-grave GHG model comparing three candidate materials for a
sanitary product anti-leak film, in **kg CO2e per kg of finished film material**:

| Material | Role |
|---|---|
| **PVA** (polyvinyl alcohol) | The incumbent |
| **LDPE** (low-density polyethylene) | Industry reference point |
| **Biomaterial film** (sodium alginate / zein / stearic acid, cast and dehydrated) | Proposed replacement |

The original 2023 process data is not available. Every figure is a
representative published value, **tagged by confidence and by system boundary**,
with both tags printed next to the number wherever it appears.

Python 3.11+, **no dependencies** (stdlib `tomllib`, hand-written SVG).

## It is a tool, not a report

Inputs go in, results come out. Every number lives in `inputs.toml`; nothing in
`lca_film/` needs editing to change a value, a formulation, an end-of-life route
or a scenario. Charts are rendered from live output.

```bash
python3 -m lca_film                                   # full report
python3 -m lca_film --table                           # comparison table
python3 -m lca_film --trace biofilm/composting        # line-by-line arithmetic
python3 -m lca_film --list-scenarios                  # what scenarios exist
python3 -m lca_film --scenario harmonised_boundary    # run one
python3 -m lca_film --compare                         # scenarios side by side
python3 -m lca_film --boundaries                      # system-boundary audit
python3 -m lca_film --sensitivity                     # what moves the answer
python3 -m lca_film --placeholders                    # what still needs a source
python3 -m lca_film --svg out/chart.svg --csv out.csv # artefacts
python3 -m lca_film --inputs mine.toml                # a different dataset

python3 -m unittest discover -s tests                 # 71 tests
```

Change one input without touching the file:

```bash
python3 -m lca_film --set biofilm/component/alginate=6.0 --table
python3 -m lca_film --scenario harmonised_boundary \
                    --set biofilm/component/zein=2.0 --trace biofilm/composting
```

Override paths are `<material>/stage/<id>`, `<material>/component/<id>` and
`<material>/eol/<id>`. A `--set` value is tagged `placeholder` on purpose: a
number typed at a shell prompt has no source behind it, and the flag says so.
Overrides are applied to the raw input tables *before* validation, so a scenario
cannot smuggle in a `literature` tag with no citation.

## Results

Two scenarios, because the honest answer depends on a sourcing decision:

```
                                        default   harmonised   food-database
LDPE        -- incineration                4.95         4.95            4.95
LDPE        -- landfill                    2.10         2.10            2.10
PVA         -- biodegradation (aqueous)    4.66         4.66            4.66
PVA         -- incineration                4.66         4.66            4.66
PVA         -- landfill                    2.76         2.76            2.76
Biomaterial -- industrial composting      14.70 !!      4.33 !!        15.39 !!
Biomaterial -- landfill                   15.09 !!      4.72 !!        15.78 !!
Biomaterial -- incineration               14.45 !!      4.08 !!        15.14 !!
                                          !! = placeholder-based
```

### Why the biomaterial moves by 4x between those columns

Not a bug, and not the biogenic credit: **a system-boundary mismatch in the
source data.**

- LDPE and PVA use polymer eco-profiles. PlasticsEurope's declared unit is
  *1 kg of unpacked resin at production site out* — no packaging, no storage, no
  retail transport, no land-use change.
- Alginate and stearic acid central values come from CarbonCloud's ClimateHub, a
  **food-ingredient** database whose stated boundary runs *from agricultural
  inputs to the retail shelf*, covering agriculture, transport, refinement,
  **packaging, storage** and waste, with deforestation in its agricultural
  engine.

Adding a packaged-food-at-shelf figure to an unpacked-resin-at-gate figure and
comparing the totals overstates the bio-based material by an unknown amount. The
model now records a `boundary` on every input, audits it against the study
target, and prints the mismatch with its **direction of bias** next to the
results. `--scenario harmonised_boundary` substitutes the lowest independently
sourced values on a comparable industrial basis.

Neither column is the answer. The default is pessimistic for the biomaterial;
the harmonised scenario is optimistic, because the alginate substitute is a
lower bound rather than a best estimate. The truth sits between roughly 4.3 and
14.7, and closing that gap needs supplier-specific data, not more searching.

### The ecoinvent stearic acid figure could not be retrieved

The `ecoinvent` *stearic acid production* dataset exists (v3.6 through v3.10) and
is the correct source for this input. It is not in the model because:

- **Climatiq**, which indexes it, states it cannot publish raw ecoinvent factors
  under its licence terms — so this is a licensing wall, not a fetching problem.
- The **ecoinvent portal**, **GLAD**, and journal hosts carrying papers that cite
  the dataset are all blocked by this environment's egress policy.

Rather than leave a food-database figure on the wrong boundary, the input is now
**interpolated between two published cradle-to-gate anchors on the same palm
oleochemical chain** and tagged `DER`, with the bracket pinned by tests. If you
have ecoinvent access, replacing it is a one-line edit to `inputs.toml` and the
single easiest upgrade left in this model.

### What the model says

1. **The biogenic carbon credit is applied, and it is small.** −1.66 kg CO2e/kg,
   computed from the blend's actual 45.3% carbon content. Even at its most
   favourable it cannot offset a raw-material burden of 3.6–14.8.
2. **Alginate dominates, and it is genuinely high-impact.** Three independent
   sources agree: CarbonCloud 21.29; a seaweed biorefinery at ~20.8 unallocated;
   alginate composite films reported at 3–7x PLA and PET, i.e. ~7–20. Seaweed
   drying and extraction chemistry are the hotspots. Bio-based is not low-carbon
   by default.
3. **Zein alone carries 239 kg CO2e/kg of range**, ~150x the next most uncertain
   input. Everything else is noise until that is closed.
4. **PVA looks decent on GWP and that is the trap.** Its biodegradation range
   (0.40–2.00) goes *down* when less of it mineralises, because the polymer
   persists as fragments instead. A lower number there is not an improvement.
5. **Composting is not carbon-negative.** 5% of carbon stays in the compost, but
   2% of released carbon leaving as CH4 at GWP100 = 27 costs more than that
   credit is worth.

## Confidence tags

Printed with every number, never in a separate notes section.

| Tag | Meaning | Enforced by the loader |
|---|---|---|
| `LIT` | Literature-backed | A `source` is **required**, or loading fails |
| `DER` | Derived by calculation | A `derivation` is **required**; tests re-derive the value from molar masses |
| `EST` | Industry-typical estimate | Defensible order of magnitude, not traced |
| `PLACEHOLDER` | No credible figure found | Any result consuming one is flagged `!! PLACEHOLDER-BASED` |

A result takes the **weakest** tag of its inputs, so one unsourced blend
component taints the blended figure and every total built on it. In the chart,
flagged bars are hatched and red-outlined so the warning survives being
screenshotted out of context.

Boundary is tracked **separately** from confidence on purpose. Confidence asks
"how well do we know this number"; boundary asks "is this even the right
quantity to add here". A value can pass the first and fail the second, and that
is the more dangerous failure because nothing looks broken.

## Auditing a number

`--trace` prints the arithmetic, not just the answer:

```
$ python3 -m lca_film --trace biofilm/composting

STEP 1. Raw materials, built up from the formulation
  Component              Mass  x  kg CO2e/kg  =  Contribution  Tag           Boundary
  Sodium alginate        0.60  x       21.29  =       12.7740  [LIT]         retail_shelf
  Zein                   0.30  x        3.00  =        0.9000  [PLACEHOLDER] factory_gate
  Stearic acid           0.10  x       11.20  =        1.1200  [LIT]         retail_shelf
  Raw material subtotal                                14.7940

STEP 2. Full account
  1. Raw materials (blend)                    +14.7940  running total  +14.7940
  2. Processing (casting + dehydration)        +0.3000  running total  +15.0940
  3. Biogenic carbon credit (uptake)           -1.6608  running total  +13.4332
  4. End of life: industrial composting        +0.1000  running total  +13.5332
  5. End of life: biogenic carbon released     +1.8568  running total  +15.3900
  TOTAL                                       +15.3900  !! PLACEHOLDER-BASED

STEP 3. Biogenic carbon check
  Credit applied at uptake          -1.6608
  Returned at end of life           +1.8568
  Net biogenic carbon               +0.1960
```

## Where the numbers come from

| Input | Value | Boundary | Source | Caveat |
|---|---|---|---|---|
| LDPE resin | 1.80 (1.70–2.00) | factory gate | PlasticsEurope LDPE eco-profile | European average |
| LDPE incineration | 2.90 (2.80–3.14) | eol | Combustion of fossil carbon | Upper bound is stoichiometric max; 2.90 implies ~92% oxidation |
| PVA resin | 2.36 (2.36–3.40) | factory gate | [Kuraray KURARAY POVAL™ LCA, 2024](https://www.kuraray-poval.com/further-news/kuraray-performs-lcas-to-make-the-sustainability-of-its-products-more-transparent) | **Manufacturer's own site LCA — a best case, not an industry average.** Kuraray states it is ~30% below the database average, implying ~3.4 generic; that is the upper bound |
| Sodium alginate | 21.29 (4.00–21.30) | **retail shelf** ⚠ | [CarbonCloud ClimateHub E401](https://apps.carboncloud.com/climatehub/product-reports/id/1360585117747) | **Boundary mismatch.** Corroborated at ~20.8 by a seaweed biorefinery (unallocated, so an upper bound) and by alginate composites at 3–7x PLA/PET. Floor 4.00 from Sargassum calcium-alginate bioplastic, 4–5.9 ([RSC *Green Chem.* 2023, **25**, 5501](https://pubs.rsc.org/en/content/articlelanding/2023/gc/d3gc01019h)) |
| Stearic acid | 4.30 (3.40–5.30) `DER` | factory gate | Interpolated between [Shah et al., *J. Surfactants Deterg.* 2016, **19**, 1333–1351](https://doi.org/10.1007/s11743-016-1867-y) (palm-kernel fatty alcohol 5.27, petro 2.97) and RSPO crude palm oil 3.41 | **Not a measured stearic acid figure.** Stearic acid is the feedstock plus splitting, fractionation and hydrogenation; fatty alcohol is that route plus two further steps, so stearic acid brackets between 3.41 and 5.27. The ecoinvent dataset is still the right source — see below |
| PVA degradation extent | qualitative | — | [Rolsky & Kelkar, *IJERPH* 2021, **18**, 6027](https://doi.org/10.3390/ijerph18116027) vs. [SciPinion panel, 2024](https://scipinion.com/panel-findings/scipinion-expert-panel-reinforces-pva-in-laundry-products-is-readily-biodegradable/) / [ACI](https://www.cleaninginstitute.org/pva) | Genuinely contested, left contested |
| Compost carbon release | 95% | eol | Patel et al. (2018), reused across compostable-plastic LCAs | Residual ~5% retained as stabilised carbon |

`DER` figures are re-derived from chemistry in the tests, so they cannot drift:

- LDPE (C2H4)n → 85.6% C; PVA (C2H4O)n → 54.5% C → 2.00 kg CO2/kg at full oxidation
- Sodium alginate (C6H7NaO6)n → 36.4% C; stearic acid (C18H36O2) → 76.0% C; zein 53% C (typical protein)
- **Biogenic credit from the actual blend, not assumed equal to cellulose:** at
  60/30/10 the film is 45.3% biogenic carbon → **−1.66 kg CO2e/kg**. Cellulose
  would give −1.63 — within 2%, but only coincidentally: alginate's low carbon
  content and stearic acid's high one happen to cancel. Change the ratios and
  that disappears, which is why it is calculated rather than borrowed.

### Still unsourced

- **Zein** — the weakest input. The only located zein LCA (RSC *Green Chem.*
  2026) reports **760 and 5300 kg CO2e/kg** for lab-scale solvent extraction,
  three orders of magnitude above any plausible commercial value. The central
  3.00 is a proxy from corn wet-milling streams (0.65–1.75) uplifted for ethanol
  extraction and drying. The 760 upper bound is kept deliberately.
- **All three blend ratios** — reconstructed, not measured, and they move the
  raw-material total materially.
- Processing energies; landfill release fraction, methane share and capture rate.

## Limitations

- Cradle-to-grave for **material only**, per kg. Converting, distribution and use
  phase excluded as assumed equivalent — worth checking, since the three films
  will not share a basis weight. Per kg is not per unit of product performance.
- **GWP only.** Water, land use, eutrophication and toxicity are absent, and
  that is exactly where seaweed- and palm-derived materials differ most.
- No energy-recovery credit on incineration; no recycling route.
- Microplastic persistence carries no number and sits outside every total.
- Sensitivity is one-at-a-time range propagation, not Monte Carlo.

## Layout

```
inputs.toml          ALL data + scenarios -- the only file to edit
lca_film/
  confidence.py      Confidence tags and how they propagate
  boundary.py        System-boundary tracking and mismatch detection
  model.py           Data structures
  config.py          Loads, applies scenarios/overrides, strictly validates
  calculate.py       The calculation -- contains no numbers of its own
  report.py          Tables, ASCII chart, sensitivity, boundary audit, --trace
  chart.py           Dependency-free themed SVG chart
  __main__.py        CLI
tests/test_lca.py    71 tests
out/                 Generated charts (regenerate with --svg)
```
