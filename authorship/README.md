# The LLM piece, and why it is optional

Everything else here is arithmetic. This is the one part that loads a model.

`rrivera1849/LUAR-MUD` is an authorship-representation model. It embeds a draft
and your corpus and returns a cosine similarity: how much does this read like
the same author. It is the only component that can answer "is this me" rather
than "does this break a rule".

## Why it is off by default

Measured, not estimated:

    model on disk .................  319MB
    one score, cold subprocess ....  ~3.7s
      of which: model load ........  ~2.7s
      of which: encode the corpus .  ~0.8s
      of which: forward pass, 1 doc  ~0.05s

Startup dominates. Caching the corpus embedding would save the smallest term and
buy a cache-invalidation surface, so it is deliberately not built.

## The honest part, which matters more than the number

Score it by LENGTH BAND, and report NO VERDICT where the model cannot give one.

In our own evaluation the metric separated real from synthetic drafts well at
short and long lengths, and came back inconclusive in the middle band. So the
middle band returns a number with an explicitly NULL reference. It does not
pretend. A voice score that answers confidently at a length where it was never
validated is worse than no score, because it gets believed.

Run your own evaluation before trusting any band. The numbers above are ours.

## What it still cannot do

It compares style. It cannot tell you the draft is TRUE, that it used your real
experience, or that the argument is one you would make. Those need a person.
