# What we found

A plain-language summary. No background needed. The technical model, its
sources and its caveats are in [README.md](README.md).

## What this compares

Three candidate materials for the anti-leak film in a sanitary product, scored
on greenhouse gas emissions — kilograms of CO2-equivalent per kilogram of film,
counted from raw material extraction all the way through to disposal:

- **PVA** (polyvinyl alcohol) — the incumbent material
- **LDPE** (low-density polyethylene) — a conventional plastic, included as a
  reference point rather than as a candidate
- **The proposed biomaterial** — a film cast and dried from sodium alginate
  (extracted from seaweed), zein (a protein from corn) and stearic acid (a fatty
  acid, usually from palm)

Because these products are often intended to be flushable, what happens at the
end of life matters as much as what happens in the factory.

## The headline: on carbon, the biomaterial is not a win

On the best figures we could find, the biomaterial comes out **substantially
worse** than both incumbents — around 15 kg CO2e per kg, against roughly 2–5 for
PVA and LDPE.

| Material | Best end-of-life route | kg CO2e per kg |
|---|---|---|
| LDPE | landfill | 2.1 |
| PVA | landfill | 2.8 |
| PVA | flushed / biodegradation | 4.7 |
| **Biomaterial** | incineration | **15.2** |
| **Biomaterial** | composting | **15.5** |

This holds under every alternative sourcing assumption we tested. Even in the
most favourable one — which, as explained below, isn't really a fair comparison —
the biomaterial's best case is about 5.4, still above PVA's 2.8 and LDPE's 2.1.

**This is worth stating plainly because it contradicts the expected result.** The
brief for this summary assumed the biomaterial's advantage would appear once the
sourcing questions were resolved. It doesn't. Resolving them narrows the gap
considerably, but on current evidence it does not reverse it.

Almost all of the difference is **one ingredient**. Sodium alginate is about 57%
of the film by weight and carries by far the largest footprint of the three
components. Seaweed drying and the chemicals used to extract the alginate are
the reasons. Three independent sources agree it is genuinely high-impact, so
this is not an artefact of one bad number. Bio-based does not mean low-carbon.

## But carbon isn't the whole question — and for a flushable product, it may not be the main one

PVA scores well here partly because of something the model cannot score at all.
Its end-of-life figure gets *better* the less of it actually breaks down — because
undegraded polymer isn't emitting carbon, it's persisting in the environment as
fragments. Whether PVA genuinely biodegrades in real wastewater treatment is
actively disputed in the literature, and for a product designed to be flushed
that is precisely the question that matters.

The biomaterial's real case is that it degrades without leaving that question
open. That is a genuine advantage, and greenhouse-gas accounting is simply the
wrong instrument for measuring it. A decision made on carbon alone would pick
the wrong material here; a decision made on persistence alone would pick the
other wrong one.

One more caveat that could move the answer: everything above is per kilogram of
material. The three films will not need the same thickness to do the same job.
If the biomaterial needs less material per product, the comparison shifts in its
favour — and nobody has measured that yet.

## Two things that emerged from building the model

**1. The alginate figure is measuring the wrong thing, and we can't fix it yet.**
The alginate number comes from a food-ingredient database that counts everything
up to the supermarket shelf, including packaging, warehousing and delivery. The
PVA and LDPE numbers come from plastics industry data that stops at the factory
gate. Adding those together and comparing the totals is not a like-for-like
comparison — it inflates the biomaterial by an amount we know the *direction* of
but not the *size*. We could not find a factory-gate figure for purified
alginate, and inventing a correction would be worse than leaving the mismatch
visible, so the model flags it rather than papering over it.

**2. Two other figures were wrong in ways that looked perfectly fine.** One was
a stearic acid number on the same mismatched basis, now replaced. The other was
more instructive: a "range" for the biomaterial that appeared to span 3 to 243
kg CO2e per kg. That wasn't uncertainty — it was two different sources measuring
two different things (one measured a finished composite film, another measured a
laboratory experiment) stacked together as though they were high and low
estimates of the same quantity. Separating those out narrowed the range to
roughly 10–17 without any new evidence at all. A wide range can be a sign that
you're confused about what you're measuring, not that the thing is uncertain.

## How much to trust these numbers

Not all inputs are equally solid, and the model labels each one:

- **Properly sourced** — the LDPE and PVA manufacturing figures, and the alginate
  figure (subject to the mismatch above).
- **Calculated** — the zein and stearic acid figures. These are worked out from
  published anchors rather than measured directly, and each rests on a stated
  assumption. The credit for plant-based carbon locked into the film is also
  calculated, but from the recipe below, so it inherits that recipe's status.
- **Estimated** — the film-making energy for all three materials, and most of
  the disposal-route details.
- **Recalled** — the biomaterial recipe itself (0.8 g alginate, 0.3 g zein,
  0.3 g stearic acid), which comes from memory rather than a lab record.

That last category is why every biomaterial figure in this model carries a
warning marker. The recipe is very likely right, but it cannot be checked
against anything, and a model whose job is to be defensible shouldn't pretend
otherwise.

**What would most change the answer**, in order: a factory-gate alginate figure
that resolves the mismatch; a measured rather than calculated zein figure; and
confirmation of the recipe from a lab record. The alginate question is worth about six
times more than the next one down, and thirteen times more than the stearic acid
question.

**The bottom line:** on greenhouse gases alone, the biomaterial currently loses,
and not narrowly. The case for it has to be made on end-of-life behaviour, on
material efficiency per product, or on impacts this model doesn't measure — and
those are real arguments, just not carbon ones.
