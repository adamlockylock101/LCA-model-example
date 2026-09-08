# Source acceptance criteria

What a candidate figure must **state** before it is allowed into `inputs.toml`
as a `literature`-tagged value on the `factory_gate` boundary.

This exists because three inputs have already been wrong in three different
ways: stearic acid was on the wrong boundary, alginate's low bound measured a
different product, and zein's high bound measured a laboratory. Each looked like
a sourced number. The fix is not more searching — it is knowing what to reject.

**If a candidate does not state an item marked (blocking), it is not usable.**
Record it as a `scope_variant` instead, with `comparable = false`.

---

## Sodium alginate

### Product identity
- **(blocking)** Purified **sodium alginate**, at a stated grade — not a
  composite, blend, film, bead, or "alginate-based material".
- If it *is* a composite, the **alginate mass fraction** must be stated so a
  per-kg-alginate figure can be back-calculated. Without that fraction the
  number cannot be used at any confidence.
- **(blocking)** Functional unit is **1 kg of alginate** — not 1 kg of seaweed,
  not 1 kg of a product containing alginate, not a volume of extract.

### Yield
- **(blocking)** **kg alginate per kg dry seaweed** (or per kg wet with moisture
  content stated). Per-kg footprint scales inversely with yield, and both
  alginate LCAs found name yield as a main hotspot. A figure without a yield
  basis cannot be corrected, compared, or scaled.

### Feedstock
- **(blocking)** Species (*Laminaria*, *Ascophyllum*, *Macrocystis*, *Sargassum*…).
- **(blocking)** Cultivation status: **cultivated / wild-harvested / beach-cast
  or bloom waste**, and the allocation applied to it. A waste feedstock under
  cut-off carries near-zero upstream burden; a cultivated one carries all of it.
  This single distinction may explain most of the 4 vs 21 gap.

### Boundary — an explicit include/exclude list
- **(blocking) Seaweed drying** — in or out. It is one of the two named hotspots
  in seaweed LCAs, and these studies commonly exclude it "for consistency with
  prior work".
- Milling; transport of seaweed to plant; equipment/infrastructure.
- **(blocking)** Packaging, storage and retail transport must be **excluded**
  for factory-gate comparability.
- **(blocking)** Land-use change: stated either way.

### Allocation
- **(blocking)** If from a biorefinery: allocation basis (mass / economic /
  energy / system expansion) and the **alginate's share**. A figure assigning
  100% to alginate must say so — that is an upper bound, not a result.

### Method
- Impact method and GWP version (IPCC AR5 vs AR6, GWP100); biogenic CO2 treatment.
- Geography and reference year — drying is energy-intensive, so grid mix matters.

### Reject outright
Reported only as a **ratio** to another material; per kg of composite with no
alginate fraction; lab-scale; no yield stated.

---

## Zein (industrial, with solvent recovery)

### Scale
- **(blocking)** **Industrial or commercial scale**, or a pilot/lab study that
  reports a **separately modelled industrial scenario** with its scale-up basis
  stated. A bench figure is disqualifying: the only published zein LCA reports
  760 and 5300 kg CO2e/kg, of which essentially all is laboratory solvent.

### Solvent — the determining variable
- **(blocking)** **Solvent recovery rate** as an explicit percentage. The
  published study's own variables include the solvent management method, which
  is why its two scenarios differ by 7x. A figure without a stated recovery rate
  cannot be interpreted at all.
- **(blocking)** Solvent identity (aqueous ethanol, isopropanol, ethyl lactate…)
  and **kg solvent per kg zein**, gross and net of recovery.

### Feedstock route
- **(blocking)** **Corn gluten meal (wet mill)** or **DDGS (dry mill)** — different
  processes, yields and purities.
- **(blocking)** **Co-product allocation of the corn burden**: mass, economic, or
  cut-off as a residue. This decides whether corn farming appears in the number
  at all.
- Yield: kg zein per kg CGM/DDGS, and the zein content of the feedstock.

### Grade
- Food vs technical grade. Purification is where the energy goes, and a film
  former may not need food grade.

### Boundary
- Same explicit include/exclude list as alginate: drying, milling, transport,
  infrastructure, packaging. Packaging and retail out for factory-gate.

### Method
- Impact method, GWP version, geography, reference year.

### Reject outright
Lab-scale with no industrial scenario; no solvent recovery rate; per kg of a
zein-containing product rather than per kg zein.

---

## Applying this

A candidate meeting every blocking item → `confidence = "literature"`,
`boundary = "factory_gate"`, with `unquantified` listing whatever it still does
not pin down.

A candidate failing any blocking item → `[[...scope_variants]]` with
`comparable = false` and `why_not_comparable` naming the failed item. The loader
enforces that such a value can never become a `low` or `high` bound.
