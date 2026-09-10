# Design notes

Why each mechanism in [`START-HERE.md`](START-HERE.md) exists. None were
designed up front; each came out of a specific failure.

Most of the input figures were retrieved with an AI assistant. Each failure
below was a real published number, correctly transcribed, with a real citation
attached — wrong in a way that neither a plausibility check nor a second look at
the citation would surface. That is why each fix is a mechanism rather than a
corrected value.

---

## Failure 1 — the right number, on the wrong boundary

**Accepted:** stearic acid at 11.20 kg CO2e/kg, from a food-ingredient database.
Correctly retrieved, correctly cited, correct for what it measured.

**Wrong because:** that database's declared scope runs to the *retail shelf* —
it includes packaging, storage, retail transport and land-use change. The
figures it was being summed with were polymer eco-profiles whose declared unit
is *1 kg of unpacked resin at production site out*. Two different questions,
added together, producing a total that was wrong in a direction nobody could
see.

**Why it was hard to catch:** plausible range, reputable source, right units.
But matching units are not matching scope, and units are what gets checked.

**What got built:** `boundary` as a first-class field on every input, tracked
*separately* from confidence, because they ask different questions — "how well
do we know this number" versus "is this even the right quantity to add here."
The loader audits every input against the study's declared target boundary, and
mismatches print next to the results with their **direction of bias** — which
way the total is wrong, not just that it is.

**The value itself** was replaced with a derived factory-gate figure, bracketed
between two published anchors on the same process chain (crude palm oil at 3.41,
one step upstream; fatty alcohol at 5.27, one step downstream) and tagged
`DERIVED` rather than `LITERATURE`, because a bracket is not a measurement.

## Failure 2 — a number that measured a different product

**Accepted:** 4.00 kg CO2e/kg as the *low bound* of the alginate range. Peer
reviewed, recent, in a strong journal.

**Wrong because:** it measured a finished *Sargassum calcium alginate composite
bioplastic* — a different material, from a waste-class feedstock carrying almost
no upstream burden, on a boundary that commonly excludes the drying step that
dominates the process. It was not a low estimate of this quantity. It was an
accurate measurement of a different quantity.

**Why it was hard to catch:** as a range bound it was invisible. A wide range
reads as appropriate humility. The model was reporting **3.49 – 242.90** and
that looked like honest uncertainty, when it was actually the model announcing
that it had added up incompatible things. A range is the one place where a
wrong number *improves* how rigorous the output appears.

**It had also propagated into the analysis.** A scenario called
`harmonised_boundary` had been built on top of it, substituting the 4.00 figure
and presenting the result as *the like-for-like comparison* — a product mismatch
dressed up as a boundary correction. That scenario was deleted, with the
reasoning left in place at [`inputs.toml:418`](inputs.toml) so nobody rebuilds
it.

**What got built:** `ScopeVariant`, a distinct type from a range bound. A
variant must declare what it actually measured, and one marked
`comparable = false` must state `why_not_comparable`. The loader **refuses** to
let such a value serve as a `low` or `high` — a hard failure at load time, not a
warning. Variants stay visible and runnable as declared scenarios
(`--scenario sargassum_route`), so the only low figure in the literature isn't
buried; it just can't pretend to be a bound.

The reported range fell to **10.32 – 17.40**. No evidence changed.

## Failure 3 — a number that measured a laboratory

**Accepted:** 760 kg CO2e/kg as the *high bound* for zein. Same functional unit,
same nominal boundary as the target. On paper, comparable.

**Wrong because:** it was a bench-scale solvent inventory with no solvent
recovery. At 760, corn upstream is under 0.3% of the total — the figure is
essentially a measurement of laboratory solvent disposal. The gap was scale, and
scale is not a scope field anyone thinks to check.

**And the model's own record of it was wrong.** The source study reports *four*
scenarios; the note in `inputs.toml` had captured only the two worst, making the
paper look an order of magnitude more damning than it is. A transcription error
inside a system built to catch them, which is why the tests re-derive `DERIVED`
values from chemistry rather than trusting the note.

**What got built:** [`SOURCING.md`](SOURCING.md) — acceptance criteria written
*before* the next search, listing what a candidate figure must state to be
usable, with blocking items marked. For zein: industrial scale, an explicit
solvent recovery percentage, feedstock route, allocation basis. For alginate:
extraction yield, species, cultivation status, an explicit boundary
include/exclude list.

**The fix for bad retrieval is not more searching, it is knowing in advance what
to reject.** A candidate failing any blocking item is recorded as a
`ScopeVariant`, not argued about.

The replacement value was derived from the study's best scenario and its own
finding that ≥95% of impact is extraction solvent:
`107 × (0.95 × (1 − recovery) + 0.05)`, giving 6.37 at 99% recovery and 10.43 at
95%. The recovery rate is recorded as an **assumption, not a source** — the
paper's own reuse case reaches only 67%, which would give 38.89. The derivation
is in the file, so anyone can disagree with the assumption rather than the
number.

## Failure 4 — the tooling, not the sourcing

Two documentation edits were applied as unasserted string replacements. The
target text had already moved, so both silently did nothing and reported
success. The result was a README carrying stale figures **alongside** correct
ones — worse than either, because partial correctness is what makes a document
trustworthy enough to quote from.

The fix was a process rule: every edit asserts that it matched, and a failed
match is an error. A silent no-op is the worst failure mode available to an
automated edit, because it reports success.

**It recurred.** Reviewing this repository in September 2026, three places still
told the reader to run `--scenario harmonised_boundary` — the scenario deleted
in Failure 2. One of them was live output: a warning printed in the report,
still describing stearic acid as a retail-shelf figure it had stopped being two
commits earlier, and directing the reader to a command that exits with an error.
Fixed in the same commit as these notes.

The point is not "be more careful". It is that **prose describing a model is
unversioned state.** The tests asserted that derived values matched the
chemistry; nothing asserted that the documentation matched the code.

**What got built** — `TestDocumentationMatchesTheModel`, four tests that parse
the README and check it against a live run:

- every figure in the results table, both scenarios, both range bounds, and the
  `!` unverifiable-input marker
- every `value (low–high)` in the sources table must be a real input
- every number in the worked `--trace` example must appear in real trace output
- every `python3 -m lca_film …` command in the README and `START-HERE.md` is
  extracted and **executed**; a non-zero exit fails the suite

The last is the direct fix here — a documented command that errors is now a
broken build — and the only one that cannot itself go stale, because it runs the
thing rather than describing it. Each check was verified by mutation: change a
digit, drop an `!`, point a command at the deleted scenario, confirm the suite
goes red for that reason.

---

## Two judgment calls

**Refusing to build the harmonised scenario.** The alginate boundary mismatch is
real and known to bias the result high. The obvious move is to correct it and
report the corrected comparison. The model doesn't, because the correction's
*size* is unknown — and a plausible invented adjustment would have reintroduced
exactly the error the system exists to catch, this time with the system's own
authority behind it. The mismatch stays flagged and uncorrected. An open,
labelled gap beats a closed, invented one.

**Ranking `RECALLED` below `ESTIMATE`.** The blend ratios turned out to be
recalled from a 2023 project rather than recorded, and none of the four existing
tags fit. The fifth was ranked *below* a generic industry estimate, which is
counterintuitive: a recollection of the real formulation is more *relevant* than
a generic figure. But **verifiability has to drive the ranking, not relevance.**
It stays distinct from `PLACEHOLDER` because a placeholder stands in for a
number nobody has, while a recalled value is a real statement that cannot be
audited. Both make a result unverifiable; only one means it is invented.

## What I would do differently

- **Write the acceptance criteria first.** `SOURCING.md` was written after the
  third failure. Two of the three would not have happened.
- **Bind the prose to the model from the start.** Now done, but only after
  Failure 4 had happened twice. Documentation drift is the same thing as an
  unsourced number — a confident claim with nothing checking it — and it went
  undefended for eight commits while the numbers had four mechanisms guarding
  them.
- **Extract the provenance layer.** It is fused to this study, and it is the
  part that generalises.
