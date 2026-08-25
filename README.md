# voice-loop

**Make AI write in your voice without fine-tuning a model.** A local-first
Python toolkit that learns your writing style from work you already have,
scores every draft against your measured style fingerprint, and learns from
every edit you make.

If you ever told Claude or ChatGPT "write like me" and got back something that
sounds like a press release, this is the fix. No GPU, no vector database, no
cloud account, no fine-tuning run. The core imports only the Python standard
library.

```bash
git clone https://github.com/assafkip/voice-loop && cd voice-loop
pip install -e .
voiceloop --help
```

## Who this is for

- Founders and consultants who send email, post on LinkedIn, and never want to
  proofread AI drafts for tone again
- Engineers building Claude skills, GPTs, or agent pipelines that must output
  text in a specific human voice
- Anyone who tried prompt-based style guides, then prompt engineering, then
  gave up

## The loop (why not just prompt harder)

Every other approach trains on your published work or describes your voice in
adjectives. Both fail the same way: nothing tells the system what you actually
wanted when you threw a draft away.

voice-loop closes that loop:

1. **Corpus.** Feed it real writing, not adjectives. LinkedIn posts, emails,
   articles, comments. Tagged by channel and era, because your LinkedIn voice
   is not your email voice.
2. **Spoken voice.** Meeting transcripts are split by speaker and only your
   lines are kept, so how you talk and how you type become one training signal.
3. **Adversarial pattern extraction.** A trait counts only if it repeats across
   samples, with quotes as proof. A second pass asks: would any decent founder
   write this? Generic gets cut.
4. **Fingerprint.** Sentence-length distribution, contraction rate, hedge
   count, paragraph rhythm, measured as percentiles FROM your corpus. Every
   draft is scored against how you statistically write, not how a model
   averages writers.
5. **Gates.** Deterministic pre-ship checks: banned-word lexicon, fake
   enthusiasm closers, engagement-bait questions, template placeholders, and an
   echo gate that refuses verbatim reuse of the prompt's own examples.
6. **Corrections.** When you change what it wrote, log WHY once:

```bash
voiceloop corrections add \
  --slug lands-a-verdict-not-a-neutral-read \
  --instruction "Take a side out loud and add the consequence." \
  --quote "I disagree with the band-aid. Leadership will point at it later."
```

That correction rides in the very next prompt. No retraining, no pipeline run.

## What it costs to run

| | llm-twin-course | voice-loop |
|---|---|---|
| Local tools | Python 3.11, Poetry, GNU Make, Docker, AWS CLI | Python |
| Cloud accounts | HuggingFace, Comet ML, Opik, OpenAI, MongoDB, Qdrant, AWS | none |
| Credentials | 9, incl. AWS key, secret, IAM role ARN | none |
| Steps to first output | 9, incl. a fine-tune and an AWS quota request | 2 |
| Running cost | ~$2/hour GPU while training or serving | $0 |
| Gated model access | request Llama-3.1-8B by hand | none |

Those numbers come from that project's own `INSTALL_AND_USAGE.md`. It teaches
production MLOps well. It is a heavy way to keep your own writing sounding
like you. If you want a full ML pipeline instead of a result, start there.

The core here imports only the standard library. The one optional component
that loads a model is documented in [`authorship/`](authorship/) and is off by
default.

## The pieces

- **The corrections log** - append-only. Every delta between a draft and your
  rewrite. This is the loop. One writer: `voiceloop corrections add`.
- **A measured fingerprint** - bands computed from your exemplars, so style
  distance is arithmetic instead of taste arguments.
- **Output gates** - each one written against a failure that actually shipped.
  A gate for a hypothetical is a rule you will fight later.
- **An echo gate** - the prompt's own examples are fluent and on-voice by
  construction, which makes them the text most likely to ship verbatim. This
  refuses that.
- **A biography check** - style and TRUTH are different questions. Claims about
  your career are checked against a facts file, separately from tone.
- **An authorship metric** - optional, see [`authorship/`](authorship/).

## Frequently asked

**Is this fine-tuning?** No, and that is the point. Fine-tuning freezes your
voice into weights at training time. This keeps it in files you can read,
edit, and diff, and a correction takes effect on the next prompt instead of
the next training run.

**Does it work with Claude, ChatGPT, Gemini, or local models?** Yes. It sits
next to whatever model you use: it builds the style context you paste or inject
into prompts, and it scores the draft that comes back. Model-agnostic by
construction.

**How much writing do I need?** The reference build ran on about 120 pieces.
More is better; the fingerprint needs enough samples to compute percentiles.

**Does my private writing leave my machine?** No. There is no cloud component
and no telemetry. Your corpus stays in `corpus/` and ships empty for exactly
that reason.

**Can I use it for a whole team's shared voice?** The mechanism does not care
whose corpus it reads, but every quality claim here was measured against one
writer's corpus. Multi-author corpora are untested; treat it as single-writer
until measured otherwise.

## What this does not solve

Every check here is a NO check. They prove nothing is wrong. They cannot prove
anything is right.

That is not a hedge, it happened: a draft cleared every gate with zero
violations while using none of the author's real experience. Clean and empty.
The fix was not another gate. It was giving the writer real material to reach
for.

A system that can only say no still needs someone who knows what yes looks
like.

## License

MIT.
