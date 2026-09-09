# Design notes

Why each mechanism in [`START-HERE.md`](START-HERE.md) exists. None of them were
designed up front. Each was built in response to a specific failure, and the
failures are more instructive than the design.

The model was built with heavy use of an AI coding assistant, including for the
literature retrieval that produced most of the input figures. That matters here
for one reason: **every sourcing failure below looked exactly like a success at
the moment it was accepted.** Each was a real published number, correctly
transcribed, with a real citation attached. What made them wrong was a property
of the number that neither a plausibility check nor a second look at the
citation would surface.

That is the defining characteristic of retrieval-assisted quantitative work, and
it is why the response in each case was to build a mechanism rather than to
correct a value. Correcting the value fixes one number. The mechanism catches
the next one, including the ones nobody has thought to look for yet.

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

**Why it was hard to catch:** nothing looked broken. The number was in a
plausible range, from a reputable source, in the right units. Units matching is
not scope matching, and unit-checking — the reflex most engineers have — gives
false comfort here precisely because it passes.

**What got built:** `boundary` as a first-class field on every input, tracked
*separately* from confidence, because they ask different questions — "how well
do we know this number" versus "is this even the right quantity to add here."
The loader audits every input against the study's declared target boundary, and
mismatches print next to the results with their **direction of bias**, so a
reader knows not just that a number is off but which way.

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
dressed up as a boundary correction, and the most confidently wrong thing the
model ever produced. That scenario was deleted, and the reasoning left in place
at [`inputs.toml:418`](inputs.toml) so nobody rebuilds it.

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
inside a system built to prevent transcription errors — which is the honest
argument for why the tests re-derive `DERIVED` values from first principles
rather than trusting the recorded note.

**What got built:** [`SOURCING.md`](SOURCING.md) — acceptance criteria written
*before* the next search, listing what a candidate figure must state to be
usable, with blocking items marked. For zein: industrial scale, an explicit
solvent recovery percentage, feedstock route, allocation basis. For alginate:
extraction yield, species, cultivation status, an explicit boundary
include/exclude list.

The insight it encodes: **the fix for bad retrieval is not more searching, it is
knowing in advance what to reject.** Three inputs had been wrong in three
different ways, and in each case a specification would have caught it at the
point of acceptance rather than three commits later. A candidate failing any
blocking item gets recorded as a `ScopeVariant`, not argued about.

The replacement value was then derived transparently from the study's best
scenario and its own stated finding that ≥95% of impact is extraction solvent:
`107 × (0.95 × (1 − recovery) + 0.05)`, giving 6.37 at 99% recovery and 10.43 at
95%. The recovery rate is recorded as an **assumption, not a source** — the
paper's own reuse case reaches only 67%, which would give 38.89. The derivation
is in the file, so anyone can disagree with the assumption rather than the
number.

## Failure 4 — the tooling, not the sourcing

Worth including because it is unflattering and because it recurred.

Two documentation edits were applied as unasserted string replacements. The
target text had already moved, so both silently did nothing and reported
success. The result was a README carrying stale figures **alongside** correct
ones — worse than either, because partial correctness is what makes a document
trustworthy enough to quote from.

The fix was a process rule: every edit asserts that it matched, and a failed
match is an error rather than a no-op. Not a clever mechanism — just the
recognition that a silent no-op is the worst available failure mode for an
automated edit, and that "it ran without errors" is not evidence that it did
anything.

**It recurred.** Reviewing this repository in September 2026, three places still
told the reader to run `--scenario harmonised_boundary` — the scenario deleted
in Failure 2. One of them was live output: a warning printed in the report,
still describing stearic acid as a retail-shelf figure it had stopped being two
commits earlier, and directing the reader to a command that exits with an error.
Fixed in the same commit as these notes.

The lesson isn't "be more careful." It is that **prose describing a model is
unversioned state**, and this project had no mechanism binding it to the model
it describes — while having an elaborate one for the numbers. The tests assert
that derived values match the chemistry; nothing asserted that the documentation
matched the code. That asymmetry is the actual defect, and it is still open.

---

## Two judgment calls worth defending

**Refusing to build the harmonised scenario.** The alginate boundary mismatch is
real and known to bias the result high. The obvious move is to correct it and
report the corrected comparison. The model doesn't, because the correction's
*size* is unknown — and a plausible invented adjustment would have reintroduced
exactly the error the system exists to catch, this time with the system's own
authority behind it. The mismatch stays flagged and uncorrected. An open,
labelled gap beats a closed, invented one.

**Ranking `RECALLED` below `ESTIMATE`.** When the blend ratios turned out to be
recalled from a 2023 project rather than recorded, none of the four existing
tags fit. A fifth was added, ranked *below* a generic industry estimate — which
is counterintuitive, since a recollection of the actual formulation is far more
*relevant* than a generic figure. But for a model whose entire purpose is
defensibility, **verifiability has to drive the ranking, not relevance.** It is
kept distinct from `PLACEHOLDER` because the two mean genuinely different
things: a placeholder stands in for a number nobody has, while a recalled value
is a real statement about this specific film that simply cannot be audited. Both
make a result unverifiable; only one means the number is invented.

## What I would do differently

- **Write the acceptance criteria first.** `SOURCING.md` was written after the
  third failure. Two of the three would not have happened.
- **Bind the prose to the model.** Every figure quoted in the README should be
  generated from the model or asserted against it by a test. Failure 4 happened
  twice for want of this.
- **Extract the provenance layer.** It is fused to this study, and it is the
  part that generalises.
