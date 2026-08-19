# voice-loop

**A voice system that learns from the drafts you rejected, not just the ones you published.**

Every other tool in this category trains on your published work. That is the
half of your writing you already agreed with. The half that tells a system what
you actually want is the draft you threw away, and almost nothing captures it.

This does. It is the whole idea.

```bash
# a draft came back wrong. You rewrote it. Log WHY, once:
voiceloop corrections add \
  --slug lands-a-verdict-not-a-neutral-read \
  --instruction "Take a side out loud and add the consequence. Do not just describe the mechanism." \
  --quote "I disagree with the band-aid. Leadership will point at it later and ask what happened."
```

That line is appended to `corpus/corrections.jsonl` and rides in the very next
prompt. No retraining, no pipeline run, no cloud.

## Why this shape

The reference implementation for writing in your own voice is
[decodingai-magazine/llm-twin-course](https://github.com/decodingai-magazine/llm-twin-course)
(4,385 stars). It crawls your Medium, Substack and GitHub into a database,
streams that into a vector store, builds an instruction dataset, fine-tunes a
model on SageMaker, and deploys it behind an inference endpoint. It is a serious
build and the engineering is real.

Every arrow in it points one way: published work goes into frozen weights.

Two things follow, and neither is a criticism of the code:

1. **It cannot train on a rejected draft.** A rejected draft was never published,
   so nothing crawls it. The most informative signal about how a person writes
   has no input in the architecture.
2. **A correction has nowhere to go.** Fixing one bad sentence means retraining.
   Nobody does that, so the correction gets made by hand and evaporates.

The gap is architecture, not competence. A snapshot cannot learn; a loop can.

## What it costs to run

|  | llm-twin-course | voice-loop |
|---|---|---|
| Local tools | Python 3.11, Poetry, GNU Make, Docker, AWS CLI | Python |
| Cloud accounts | HuggingFace, Comet ML, Opik, OpenAI, MongoDB, Qdrant, AWS | none |
| Credentials | 9, incl. AWS key, secret, IAM role ARN | none |
| Steps to first output | 9, incl. a fine-tune and an AWS quota request | 2 |
| Running cost | ~$2/hour GPU while training or serving | $0 |
| Gated model access | request Llama-3.1-8B by hand | none |

Those numbers come from that project's own `INSTALL_AND_USAGE.md`. It is aimed
at teaching production MLOps, and it does that well. It is a heavy way to keep
your own writing sounding like you.

The core of voice-loop imports only the Python standard library. The one
optional component that loads a model is documented in
[`authorship/`](authorship/) and is off by default.

## The pieces

- **The corrections log** — append-only. Every delta between a draft and your
  rewrite. This is the loop. One writer: `voiceloop corrections add`.
- **A measured fingerprint** — sentence-length variance, rhythm, first-person
  rate, computed FROM your exemplars. Bands, not opinions. A draft outside them
  is flagged by arithmetic, so nobody argues about taste.
- **Output gates** — deterministic checks on the finished text. Write each one
  against a failure that actually shipped. A gate for a hypothetical is a rule
  you will fight later.
- **An echo gate** — the prompt's own examples are fluent and on-voice by
  construction, which makes them the text most likely to ship verbatim. This
  refuses that.
- **A biography check** — style and TRUTH are different questions. Keep the
  claims a piece may make about your history in a file, and check them
  separately from how it sounds.
- **The authorship metric** — optional, see [`authorship/`](authorship/).

## Install

```bash
git clone https://github.com/assafkip/voice-loop && cd voice-loop
pip install -e .
```

Then fill in `corpus/`. It ships empty on purpose: the mechanism is open source,
the voice is not. `corpus/README.md` says what each file is and who may write it.

```bash
voiceloop fingerprint   # compute your bands from your exemplars
voiceloop validate      # check the corpus for problems
```

## What this does not solve

Every check here is a NO check. They prove nothing is wrong. They cannot prove
anything is right.

That is not a hedge, it happened: a draft cleared every gate with zero
violations while using none of the author's real experience. Clean and empty.
The fix was not another gate. It was giving the writer real material to reach
for.

A system that can only say no still needs someone who knows what yes looks like.

## License

MIT.
