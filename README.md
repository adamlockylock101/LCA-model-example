# Anti-leak film LCA model

> **New here, or not a materials engineer?** Read
> **[`START-HERE.md`](START-HERE.md)** instead. This file is the full study and
> assumes the domain; that one explains what was built and why, and needs none
> of it. Or just run **`./demo.sh`** — a five-minute guided tour that ends with
> the guardrails refusing bad input.
>
> [`DESIGN-NOTES.md`](DESIGN-NOTES.md) covers why each mechanism exists: three
> sourcing failures, three structural fixes.

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

Inputs go in, results come out. Charts are rendered from live output, never
hand-drawn.

```bash
python3 -m lca_film                                   # full report
python3 -m lca_film --table                           # comparison table
python3 -m lca_film --trace biofilm/composting        # line-by-line arithmetic
python3 -m lca_film --list-scenarios                  # what scenarios exist
python3 -m lca_film --scenario sargassum_route        # run one
python3 -m lca_film --compare                         # scenarios side by side
python3 -m lca_film --boundaries                      # system-boundary audit
python3 -m lca_film --sensitivity                     # what moves the answer
python3 -m lca_film --placeholders                    # unverifiable inputs
python3 -m lca_film --svg out/chart.svg --csv out.csv # artefacts
python3 -m lca_film --inputs mine.toml                # a different dataset

python3 -m unittest discover -s tests                 # 88 tests
```

Change one input without touching the file:

```bash
python3 -m lca_film --set biofilm/component/alginate=6.0 --table
python3 -m lca_film --scenario sargassum_route \
                    --set biofilm/component/zein=2.0 --trace biofilm/composting
```

Override paths are `<material>/stage/<id>`, `<material>/component/<id>` and
`<material>/eol/<id>`. A `--set` value is tagged `placeholder` on purpose: a
number typed at a shell prompt has no source behind it, and the flag says so.
Overrides are applied to the raw input tables *before* validation, so a scenario
cannot smuggle in a `literature` tag with no citation.

## Changing the inputs

Every number lives in `inputs.toml`. Nothing in `lca_film/` needs editing to
change a value, a formulation, an end-of-life route or a scenario.

**The blend is stored as the recipe, in grams**, not as percentages:

```toml
[[materials.composition]]
id              = "alginate"
component       = "Sodium alginate"
dry_mass_g      = 0.8          # <- the recalled recipe
frac_confidence = "recalled"
```

The model normalises the grams, so hand-rounded percentages can never fail the
sum-to-one check or silently shift the blend — 57/21/21 sums to 99, the grams
do not have that problem. Solvents are excluded by construction: the water and
ethanol in the recipe evaporate during dehydration, so they carry no dry-film
mass and appear in the **processing** stage instead, not as blend components.

The biogenic carbon credit recomputes itself from the new carbon content
whenever the blend changes, and so does the end-of-life release that mirrors it.

## Results

Two scenarios, because the honest answer depends on a sourcing decision:

```
                                       default    range      sargassum route
LDPE        -- incineration               4.95   4.65- 5.54             4.95
LDPE        -- landfill                   2.10   1.86- 2.50             2.10
PVA         -- biodegradation (aqueous)   4.66   2.96- 5.85             4.66
PVA         -- incineration               4.66   4.40- 5.85             4.66
PVA         -- landfill                   2.76   2.58- 4.15             2.76
Biomaterial -- industrial composting     15.50 !  10.32-17.40           5.62 !
Biomaterial -- landfill                  15.92 !  10.77-17.78           6.04 !
Biomaterial -- incineration              15.24 !  10.08-17.09           5.36 !
                                         !  = recalled input (unverifiable)
```

The biomaterial range was **3.49–242.90** before scope variants were separated
from parametric uncertainty. Nothing about the evidence changed; the model
stopped reporting a category error as an uncertainty interval. Both remaining
spans are now tied to a **named parameter** — extraction yield for alginate,
solvent recovery rate for zein.

### Two different ways source figures disagree

The model separates them, because conflating them is how a scope error gets
laundered into a confidence interval.

**1. Boundary mismatch — different scope, same product.** LDPE and PVA use
polymer eco-profiles; PlasticsEurope's declared unit is *1 kg of unpacked resin
at production site out*. The alginate figure comes from CarbonCloud's
ClimateHub, a **food-ingredient** database running *from agricultural inputs to
the retail shelf*, including packaging, storage and deforestation. Every input
records a `boundary`; the loader audits it and the report prints each mismatch
with its **direction of bias**. Stearic acid was fixed this way. Alginate cannot
be — the correction is real but its size is unknown, and inventing one would
reintroduce the error. It stays flagged. `--boundaries`

**2. Scope variants — different product entirely.** These are published numbers
that measure something else, and they must never be range bounds:

| Was used as | Actually measures | Now |
|---|---|---|
| Alginate low bound **4.00** | A finished *Sargassum calcium alginate composite bioplastic* — different product, waste-class feedstock, boundary that commonly excludes seaweed drying | Scope variant, `--scenario sargassum_route` |
| Zein high bound **760** | A *laboratory solvent inventory*. Same functional unit, same nominal boundary — the gap is bench vs industrial scale with no solvent recovery. At 760+, corn upstream is under 0.3% of the total | Scope variant |

A variant declared `comparable = false` must state `why_not_comparable`, and the
loader **refuses** to let its value be used as a `low` or `high`. `--scenario`
can pull one by id, so a scenario cannot drift from the variant it claims to use.

**3. Unquantified uncertainty — drivers with no number.** A range is only as
meaningful as the parameter behind it. Alginate's 13.60–22.79 is *extraction
yield*; zein's 6.37–10.43 is *solvent recovery rate*. What each range does **not**
cover — biorefinery co-product allocation, the retail-shelf correction,
purification depth, species and season, whether the assumed recovery rate is
achievable — carries no defensible number and sits in an `unquantified` list
printed next to the value. A short bar in the sensitivity ranking is not a
settled input, and the report says so.

### What the model says

1. **The biogenic carbon credit is applied, and it is small.** −1.77 kg CO2e/kg,
   computed from the blend's actual 48.4% carbon content. Even at its most
   favourable it cannot offset a raw-material burden of ~14.9.
2. **Alginate dominates, and it is genuinely high-impact.** The two sources that
   measure purified alginate agree closely: CarbonCloud 21.29 and a seaweed
   biorefinery at ~20.8 unallocated. Seaweed drying and extraction chemistry are
   the hotspots. Bio-based is not low-carbon by default.
3. **Zein was under-estimated, not over-estimated.** The old 3.00 proxy came from
   corn-stream footprints and missed that ≥95% of zein's impact is extraction
   *solvent*, not feedstock. The derived industrial figure is **8.40**, and the
   sensitivity ranking is now usable: the top parametric driver is 6.92
   kg CO2e/kg, not 239.
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
| `RECALLED` | Recalled from memory, not a record | Any result consuming one is flagged `! RECALLED INPUT` |
| `PLACEHOLDER` | No credible figure found | Any result consuming one is flagged `!! PLACEHOLDER-BASED` |

`RECALLED` ranks *below* `EST` on purpose. A recollection of the actual
formulation is more **relevant** than a generic industry figure but less
**verifiable**, and for a model whose job is defensibility, verifiability is
what has to drive the ranking. It is kept distinct from `PLACEHOLDER` because
the two mean different things: a placeholder is a stand-in for a number nobody
has; a recalled value is a real statement about this specific film that simply
cannot be audited. Both make a result unverifiable; only one means the number
is invented.

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
  Component           Dry g    Frac  kg CO2e/kg  Contribution  Range width  Tag
  Sodium alginate       0.8  0.5714       21.29       12.1657       5.2514  [LIT]
  Zein                  0.3  0.2143        8.40        1.8000       0.8700  [DER]
  Stearic acid          0.3  0.2143        4.30        0.9214       0.4071  [DER]
  Raw material subtotal                                14.8871       6.5286

STEP 2. Full account
  1. Raw materials (blend)                    +14.8871  running total  +14.8871
  2. Processing (casting + dehydration)        +0.3000  running total  +15.1871
  3. Biogenic carbon credit (uptake)           -1.7746  running total  +13.4126
  4. End of life: industrial composting        +0.1000  running total  +13.5126
  5. End of life: biogenic carbon released     +1.9840  running total  +15.4966
  TOTAL                                       +15.4966  ! RECALLED INPUT

STEP 3. Biogenic carbon check
  Credit applied at uptake          -1.7746
  Returned at end of life           +1.9840
  Net biogenic carbon               +0.2094
```

`Range width` is each component's share of the raw-material range — its mass
fraction times its own low-to-high span. It answers "which component is worth
resolving next" directly: alginate carries **12.9×** the range that stearic acid
does, even after stearic acid's share doubled.

## Where the numbers come from

| Input | Value | Boundary | Source | Caveat |
|---|---|---|---|---|
| LDPE resin | 1.80 (1.70–2.00) | factory gate | PlasticsEurope LDPE eco-profile | European average |
| LDPE incineration | 2.90 (2.80–3.14) | eol | Combustion of fossil carbon | Upper bound is stoichiometric max; 2.90 implies ~92% oxidation |
| PVA resin | 2.36 (2.36–3.40) | factory gate | [Kuraray KURARAY POVAL™ LCA, 2024](https://www.kuraray-poval.com/further-news/kuraray-performs-lcas-to-make-the-sustainability-of-its-products-more-transparent) | **Manufacturer's own site LCA — a best case, not an industry average.** Kuraray states it is ~30% below the database average, implying ~3.4 generic; that is the upper bound |
| Sodium alginate | 21.29 (13.60–22.79) | **retail shelf** ⚠ | [CarbonCloud ClimateHub E401](https://apps.carboncloud.com/climatehub/product-reports/id/1360585117747), corroborated at ~20.8 by a seaweed biorefinery | **Boundary mismatch, still open.** Range is **yield-derived**: published *Laminaria digitata* yields span 30.9%–51.8% of dry biomass, and rescaling the 20.83 figure from its 33.8% yield basis across that span gives 13.60–22.79. The 4.00 Sargassum figure ([RSC *Green Chem.* 2023, **25**, 5501](https://pubs.rsc.org/en/content/articlelanding/2023/gc/d3gc01019h)) is a scope variant, not a bound |
| Zein | 8.40 (6.37–10.43) `DER` | factory gate | Derived from RSC *Green Chem.* 2026 zein LCA | **Not measured.** That study reports four scenarios — CGM 232 (IPA) / 107 (EtOH), DDGS 5300 / 760 — and attributes ≥95% of impact to extraction solvent. Taking the best (107) and rescaling that share for industrial closed-loop recovery: `107 × (0.95 × (1−recovery) + 0.05)` gives 6.37 at 99% and 10.43 at 95%. **The recovery rate is assumed, not sourced** — the paper's own reuse case (67%) would give 38.89 |
| Stearic acid | 4.30 (3.40–5.30) `DER` | factory gate | Interpolated between [Shah et al., *J. Surfactants Deterg.* 2016, **19**, 1333–1351](https://doi.org/10.1007/s11743-016-1867-y) (palm-kernel fatty alcohol 5.27, petro 2.97) and RSPO crude palm oil 3.41 | **Not a measured stearic acid figure.** Stearic acid is the feedstock plus splitting, fractionation and hydrogenation; fatty alcohol is that route plus two further steps, so stearic acid brackets between 3.41 and 5.27. The ecoinvent dataset is still the right source — see below |
| PVA degradation extent | qualitative | — | [Rolsky & Kelkar, *IJERPH* 2021, **18**, 6027](https://doi.org/10.3390/ijerph18116027) vs. [SciPinion panel, 2024](https://scipinion.com/panel-findings/scipinion-expert-panel-reinforces-pva-in-laundry-products-is-readily-biodegradable/) / [ACI](https://www.cleaninginstitute.org/pva) | Genuinely contested, left contested |
| Compost carbon release | 95% | eol | Patel et al. (2018), reused across compostable-plastic LCAs | Residual ~5% retained as stabilised carbon |

`DER` figures are re-derived from chemistry in the tests, so they cannot drift:

- LDPE (C2H4)n → 85.6% C; PVA (C2H4O)n → 54.5% C → 2.00 kg CO2/kg at full oxidation
- Sodium alginate (C6H7NaO6)n → 36.4% C; stearic acid (C18H36O2) → 76.0% C; zein 53% C (typical protein)
- **Biogenic credit from the actual blend, not assumed equal to cellulose:** at
  the recalled 57/21/21 the film is 48.4% biogenic carbon → **−1.77 kg CO2e/kg**.
  Cellulose would give −1.63, now **9% adrift**. Under the old assumed 60/30/10
  the two agreed to within 2%, and that coincidence is exactly what a cellulose
  shortcut would have relied on: doubling the stearic acid share (76.0% C, the
  most carbon-dense component) broke it. The credit is calculated from the real
  blend for this reason.

### Still unsourced

- **The blend ratios** — now the recalled recipe (0.8 g / 0.3 g / 0.3 g) rather
  than a reconstructed guess, which is a real improvement, but from memory not a
  lab record. Tagged `RECALLED`; they are why every biomaterial row is still
  flagged. **No placeholder inputs remain.**
- **A factory-gate purified-alginate figure** — the remaining boundary mismatch.
- **A measured industrial zein figure** to replace the derived one; above all a
  stated **solvent recovery rate**, the parameter the derivation turns on.

See [`SOURCING.md`](SOURCING.md) for exactly what a candidate must state before
it can be accepted — written after three inputs turned out to be wrong in three
different ways.
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
START-HERE.md        What this is, for a reader who does not want the chemistry
DESIGN-NOTES.md      Why each mechanism exists -- the failures that produced them
SOURCING.md          What a candidate source must state before it is accepted
demo.sh              Five-minute guided tour, guardrails included
inputs.toml          ALL data + scenarios -- the only file to edit
lca_film/
  confidence.py      Confidence tags and how they propagate
  boundary.py        System-boundary tracking and mismatch detection
  model.py           Data structures, incl. ScopeVariant (a different measurement,
                     never a bound) and unquantified uncertainty drivers
  config.py          Loads, applies scenarios/overrides, strictly validates
  calculate.py       The calculation -- contains no numbers of its own
  report.py          Tables, ASCII chart, sensitivity, boundary audit, --trace
  chart.py           Dependency-free themed SVG chart
  __main__.py        CLI
tests/test_lca.py    88 tests
out/                 Generated charts (regenerate with --svg)
```

Add `./demo.sh` to the command list at the top: it runs the tour, and it asserts
that each guardrail fails for the *expected reason* rather than merely failing.
