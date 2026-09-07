# Anti-leak film LCA model

A pluggable cradle-to-grave GHG model comparing three candidate materials for a
sanitary product anti-leak film, in **kg CO2e per kg of finished film material**:

| Material | Role |
|---|---|
| **PVA** (polyvinyl alcohol) | The incumbent |
| **LDPE** (low-density polyethylene) | Industry reference point |
| **Biomaterial film** (sodium alginate / zein / stearic acid, cast and dehydrated) | Proposed replacement |

The original 2023 process data is not available. Every figure in this model is a
**representative published value, tagged by confidence**, and the tag is printed
next to the number everywhere the number appears.

> **The headline result is that the comparison cannot yet be made.** On
> representative published figures the biomaterial film comes out *worse* than
> both incumbents, but its range spans two orders of magnitude because one input
> (zein) has no credible industrial figure behind it. The model is built to make
> that visible rather than to hide it behind a single confident-looking number.

---

## Running it

Python 3.11+. **No dependencies** — everything is standard library
(`tomllib` for config, hand-rolled SVG for the chart).

```bash
python3 -m lca_film                     # full report
python3 -m lca_film --table             # comparison table only
python3 -m lca_film --sensitivity       # what moves the answer most
python3 -m lca_film --placeholders      # what still needs a source
python3 -m lca_film --svg chart.svg     # chart
python3 -m lca_film --csv results.csv   # per-stage results for a spreadsheet
python3 -m lca_film --inputs mine.toml  # run an alternative dataset

python3 -m unittest discover -s tests   # 35 tests
```

## Results

```
Material / end-of-life route                        Total    Range (low - high)  Weakest      Flag
LDPE -- Incineration                                 4.95           4.65 - 5.54  EST
LDPE -- Landfill                                     2.10           1.86 - 2.50  EST
PVA -- biodegradation (wastewater / aqueous)         4.66           2.96 - 5.85  EST
PVA -- incineration                                  4.66           4.40 - 5.85  EST
PVA -- landfill                                      2.76           2.58 - 4.15  EST
Biomaterial -- industrial composting                15.39         3.49 - 242.90  PLACEHOLDER  !! PLACEHOLDER-BASED
Biomaterial -- landfill                             15.78         3.90 - 243.24  PLACEHOLDER  !! PLACEHOLDER-BASED
Biomaterial -- incineration                         15.14         3.26 - 242.60  PLACEHOLDER  !! PLACEHOLDER-BASED
```

### What this actually says

1. **The biomaterial is not obviously better.** Its raw-material burden
   (14.79 kg CO2e/kg) is dominated by sodium alginate at 21.29 kg CO2e/kg —
   roughly 12× LDPE's resin footprint. Bio-based does not mean low-carbon;
   seaweed drying and extraction yield are the hotspots in every alginate LCA
   found. The biogenic carbon credit (−1.66) is real but small against that.

2. **The zein input alone is worth 239 kg CO2e/kg of range** — about 150× the
   next most uncertain input. Every other question in this model is noise until
   a real zein figure exists. That is the single highest-value next action, and
   the sensitivity report says so directly.

3. **PVA looks decent on GWP and that is the trap.** Its end-of-life
   biodegradation range (0.40–2.00) goes *down* when less of it mineralises —
   because the polymer persists as fragments instead. A lower number on that row
   is not an improvement. This is recorded as a qualitative flag printed with the
   results, because GWP alone cannot rank that route.

4. **Composting is not carbon-negative here.** 5% of the film's carbon stays in
   the compost as a genuine credit, but 2% of the released carbon leaving as CH4
   at GWP100 = 27 costs more than that credit is worth. The model surfaces this;
   a spreadsheet that netted biogenic carbon to zero would have missed it.

5. **Landfill flatters both fossil materials.** LDPE-to-landfill is the
   lowest-emitting row in the table, purely because the carbon stays put. No
   energy-recovery credit is taken on any incineration route, which is the
   conservative choice.

## Confidence tags

Every number carries one, and it is printed with the number — never in a
separate notes section.

| Tag | Meaning | Enforced by the loader |
|---|---|---|
| `LIT` | Literature-backed | A `source` is **required**, or loading fails |
| `DER` | Derived by calculation in this model | A `derivation` is **required**, and the test suite re-derives the value from molar masses |
| `EST` | Industry-typical estimate | Defensible order of magnitude, not traced to a source |
| `PLACEHOLDER` | No credible figure found | Any result consuming one is flagged `!! PLACEHOLDER-BASED` |

**Propagation:** a result takes the weakest tag of its inputs. One placeholder
component in the blend taints the blended raw-material figure, which taints
every total built on it. A flagged row cannot be compared with an unflagged row
at face value, and the report says so on the same screen as the numbers. In the
SVG chart, flagged bars are hatched and outlined in red for the same reason.

## Changing the inputs

**All numbers live in `inputs.toml`. Nothing in `lca_film/` needs editing to
change a value, a formulation, or an end-of-life route.**

Swap a figure:

```toml
[[materials.stages]]
id         = "raw_material"
label      = "Raw material + hydrolysis of PVAc"
value      = 2.36          # <- change this
low        = 2.36
high       = 3.40
confidence = "literature"  # <- and this, if the provenance changed
source     = "Kuraray KURARAY POVAL(TM) LCA, 2024 ..."
```

Reweight the biomaterial blend by editing `mass_fraction` in the
`[[materials.composition]]` entries — the loader enforces that they sum to 1.0,
and the biogenic carbon credit recomputes itself from the new carbon content
automatically. Add an end-of-life route by appending a `[[materials.eol_routes]]`
table; it appears in every report without any code change.

## Where the numbers come from

`LIT` figures, with the caveats that matter:

| Input | Value | Source | Caveat |
|---|---|---|---|
| LDPE resin | 1.80 (1.70–2.00) | PlasticsEurope LDPE eco-profile range | European average |
| LDPE incineration | 2.90 (2.80–3.14) | Near-total combustion of fossil carbon | Upper bound is the stoichiometric max at 100% oxidation; 2.90 implies ~92% |
| PVA resin | 2.36 (2.36–3.40) | [Kuraray KURARAY POVAL™ LCA, 2024](https://www.kuraray-poval.com/further-news/kuraray-performs-lcas-to-make-the-sustainability-of-its-products-more-transparent): 2.36 kg CO2e/kg cradle-to-gate, Frankfurt (2.47 previously) | **Manufacturer's own site-specific LCA — a best case, not an industry average.** Kuraray states it is ~30% below the database average for PVOH, implying ~3.4 generic; that is the upper bound |
| Sodium alginate | 21.29 (4.00–21.30) | [CarbonCloud ClimateHub, sodium alginate E401](https://apps.carboncloud.com/climatehub/product-reports/id/1360585117747) | Corroborated at ~20.8 by a seaweed-biorefinery LCA (7042.7 kg CO2e/t dry seaweed → 338 kg alginate) — but **unallocated across co-products**, so that is an upper bound, not confirmation. Lower bound 4.00 is Sargassum calcium-alginate bioplastic at 4–5.9 kg CO2e/kg ([RSC *Green Chem.* 2023, **25**, 5501](https://pubs.rsc.org/en/content/articlelanding/2023/gc/d3gc01019h)) — different feedstock and process |
| Stearic acid | 11.20 (3.40–11.20) | [CarbonCloud ClimateHub, stearic acid E570](https://apps.carboncloud.com/climatehub/product-reports/id/3611333312577) | Single source, food-grade, almost certainly includes palm land-use change. Floor of 3.40 is RSPO-certified crude palm oil (3.41; non-certified 5.34) — feedstock only, before splitting and hydrogenation |
| PVA degradation extent | qualitative | [Rolsky & Kelkar, *IJERPH* 2021, **18**, 6027](https://doi.org/10.3390/ijerph18116027) vs. [SciPinion expert panel, 2024](https://scipinion.com/panel-findings/scipinion-expert-panel-reinforces-pva-in-laundry-products-is-readily-biodegradable/) / [ACI](https://www.cleaninginstitute.org/pva) | Genuinely contested and left contested in the model |
| Compost carbon release | 95% | Patel et al. (2018), as reused across compostable-plastic LCAs | Residual ~5% retained as stabilised carbon |

`DER` figures are computed from chemistry and independently re-derived in the
tests, so they cannot drift if someone hand-edits the config:

- LDPE (C2H4)n → 85.6% C; PVA (C2H4O)n → 54.5% C → 2.00 kg CO2/kg at full oxidation
- Sodium alginate (C6H7NaO6)n → 36.4% C; stearic acid (C18H36O2) → 76.0% C; zein taken as 53% C (typical protein)
- **Biogenic credit, computed from the actual blend, not assumed equal to cellulose:**
  at 60/30/10 the film is 45.3% biogenic carbon → **−1.66 kg CO2e/kg**.
  Cellulose would have given −1.63 — within 2%, but only by coincidence:
  alginate's low carbon content and stearic acid's high one happen to cancel.
  Change the ratios and that coincidence disappears, which is exactly why the
  credit is calculated rather than borrowed.

### Still unsourced

- **Zein raw material** — the weakest input in the model. The only located zein
  LCA (RSC *Green Chem.* 2026, zein / ethyl lactate / nanofiltration membranes)
  reports **760 and 5300 kg CO2e/kg** for lab-scale solvent extraction — three
  orders of magnitude above any plausible commercial value and dominated by
  laboratory solvent use. The central 3.00 is a **proxy**: corn wet-milling
  streams sit near 0.65–1.75 kg CO2e/kg, uplifted for the ethanol extraction and
  drying needed to isolate zein from corn gluten meal. The 760 upper bound is
  kept deliberately — it is what the only published number says, and dropping it
  would misrepresent how unresolved this is.
- **All three blend ratios** — reconstructed, not measured. Because the component
  footprints differ by ~7×, the ratio moves the raw-material total materially.
- Processing energies for all three materials (`EST`, UK grid assumption).
- Landfill release fraction, methane share and capture rate for the biomaterial.

## Limitations

- Cradle-to-grave for **material only**. Converting, distribution and use phase
  are excluded on the assumption they are equivalent across candidates — which
  is worth checking, since the three films will not have the same basis weight.
  Comparing per kg is not the same as comparing per unit of product performance.
- **GWP only.** Water, land use, eutrophication and toxicity are all absent, and
  they are precisely where a seaweed or palm-derived material would differ most.
- No energy-recovery credit on incineration; no recycling route modelled.
- Microplastic persistence carries no number and so sits outside every total.
- Sensitivity is one-at-a-time range propagation, not a Monte Carlo.

## Layout

```
inputs.toml          ALL data lives here -- the only file to edit to change a number
lca_film/
  confidence.py      Confidence tags and how they propagate
  model.py           Data structures (Quantity, Component, EndOfLifeRoute, Material)
  config.py          Loads and strictly validates inputs.toml
  calculate.py       The calculation -- contains no numbers of its own
  report.py          Text report, comparison table, ASCII chart, sensitivity
  chart.py           Dependency-free SVG chart
  __main__.py        CLI
tests/test_lca.py    35 tests
```
