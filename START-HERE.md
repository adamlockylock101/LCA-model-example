# Start here

**What this is:** a calculation engine for quantitative work where the inputs
are of wildly uneven quality, and where a confidently-stated wrong number is the
expensive failure — not a missing one.

The domain happens to be materials science: comparing the carbon footprint of
three candidate films. **Nothing on this page depends on knowing any of that.**
The domain is the test case; the engineering is the point.

Python 3.11+, standard library only, no install step, 92 tests.

---

## The problem it solves

You are assembling a number from thirty other numbers. Some are peer-reviewed,
some are engineering estimates, some were retrieved by a language model and look
authoritative.

The arithmetic doesn't care. Add a well-sourced figure to a guess and the result
renders identically to a well-sourced one. Caveats sections and spreadsheet
comments don't fix this, because they aren't attached to the number: the figure
gets copied out and the warning stays behind.

So provenance is made **structural** — part of the type, enforced by the loader,
propagated by the arithmetic, impossible to strip at render time.

## Four mechanisms

### 1. Every number is a value *and* its provenance

No impact figure is stored as a bare float. The primitive is a `Quantity`
carrying its value, how well it is known, what boundary it was measured on, its
source, and a range. (Physical constants — molar masses, carbon mass fractions —
are plain floats, since they are not claims about the world in the same way.)

```python
@dataclass(frozen=True)
class Quantity:                 # lca_film/model.py, abridged
    label: str
    value: float
    confidence: Confidence      # LIT / DER / EST / RECALLED / PLACEHOLDER
    boundary: str = "unspecified"
    low: Optional[float] = None
    high: Optional[float] = None
    source: str = ""
    derivation: str = ""
    unquantified: tuple[str, ...] = ()      # named drivers with NO number
    scope_variants: tuple[ScopeVariant, ...] = ()   # never bounds — see (3)
```

### 2. Provenance propagates by weakest link

Combining values yields **the weakest tag of its inputs**, so one unsourced
component taints its subtotal and every total built on it. The whole rule is
five lines in `confidence.py`, and it is the load-bearing one in the system:

```python
def weakest(tags: Iterable[Confidence]) -> Confidence:
    tags = list(tags)
    if not tags:
        return Confidence.DERIVED   # a total of nothing is an artefact, not a fact
    return max(tags, key=lambda t: t.rank)
```

A total can never look better-sourced than its worst ingredient. There is no
path through the code that produces an untagged number, and the renderer prints
the tag next to the value every time — in tables, in traces, and hatched into
the SVG chart so the warning survives being screenshotted out of context.

### 3. "Different scope" is a different type from "uncertain"

This is the mechanism I'd point at first.

A `low`/`high` range means *we are unsure how big this thing is*. A published
figure that measured **a different thing** is not that, and collapsing the
second into the first turns a category error into a confidence interval — which
reads as rigour and is the exact opposite of it.

So a source that measures something else is a `ScopeVariant`, a separate type.
It must declare what it actually measured, and the loader **refuses** to let a
variant marked `comparable = false` be used as a range bound. Not a warning: a
refusal, at load time.

The effect, measured on this dataset:

| | Reported range |
|---|---|
| Before scope variants existed | **3.49 – 242.90** |
| After | **10.32 – 17.40** |

No evidence changed. Two figures serving as range bounds turned out to measure a
different product and a laboratory respectively, and the type system stopped
accepting them. The old range was not a finding about the world; it was a
finding about a bug in the model.

### 4. Correctness of the *number* and correctness of the *quantity* are tracked separately

`confidence` asks "how well do we know this number". `boundary` asks "is this
even the right quantity to add here" — was it measured to the same scope as the
things it is being summed with?

A value can pass the first and fail the second, and that is the more dangerous
failure, because nothing looks broken. The totals are just wrong. Every input
records its boundary, the loader audits all of them against the study's target,
and mismatches print next to the results **with their direction of bias**, not
in a footnote.

## What the loader refuses to load

Validation runs before anything is computed, and it rejects rather than warns:

| Rule | Rationale |
|---|---|
| `confidence = "literature"` with no `source` | A citation-free citation is the failure mode being defended against |
| `confidence = "derived"` with no `derivation` | And the tests re-derive those values from first principles, so they cannot drift |
| A central value outside its own `low`/`high` | Usually means a range was updated and the value wasn't |
| A non-comparable `ScopeVariant` used as a bound | See (3) |
| A blend whose components don't sum to 1 | Composition is stored as the recipe in grams and normalised, so rounded percentages can't silently shift the mix |
| An override that sets `literature` with no source | Overrides go through the *same* validation as authored values, so a scenario can't launder an unsourced number |

## Two minutes at a terminal

```bash
./demo.sh                    # guided tour, including the guardrails refusing things
```

Or by hand:

```bash
python3 -m lca_film --table              # the answer
python3 -m lca_film --trace biofilm/composting   # every step of the arithmetic
python3 -m lca_film --boundaries         # are these numbers measuring the same thing?
python3 -m unittest discover -s tests    # 92 tests
```

The one worth running is this. Substitute a friendlier number for the input that
dominates the result:

```bash
python3 -m lca_film --set biofilm/component/alginate=6.0 --table
```

The headline figure drops from **15.50 to 6.76** — and every affected row is now
stamped `!! PLACEHOLDER-BASED`. A number typed at a shell prompt has no source
behind it, so the tool tags it as such and refuses to let the improvement look
clean. **Making the answer better automatically made it less trustworthy, and
the output says so without being asked.**

## Where to go next

| | |
|---|---|
| [`DESIGN-NOTES.md`](DESIGN-NOTES.md) | Why each mechanism exists. Three sourcing failures, three structural fixes. The most useful thing to read after this page. |
| [`SOURCING.md`](SOURCING.md) | A written specification for rejecting evidence, produced after the third failure. |
| [`README.md`](README.md) | The full study, including all the materials science. |
| `lca_film/confidence.py` | 75 lines. The whole propagation rule. |
| `lca_film/model.py` | The types, including `ScopeVariant` and its docstring. |
| `tests/test_lca.py` | 92 tests, 63 of them defending the provenance system rather than the arithmetic — including four that assert the documentation against a live run. |

## Honest limitations

- Single-domain. The provenance layer isn't extracted as a reusable library; it
  is fused to this study.
- One-at-a-time range propagation, not Monte Carlo. Correlated inputs aren't
  modelled.
- The blend ratios are recalled from a 2023 project rather than recorded, which
  is why every result for that material is flagged `RECALLED`. The model is
  honest about it rather than fixed — the fix requires a lab record that no
  longer exists.
