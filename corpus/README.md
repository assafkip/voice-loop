# corpus/

Your writing lives here. This directory ships EMPTY on purpose: the mechanism is
the open-source part, your voice is not.

| File | What it is | Who writes it |
|---|---|---|
| `identity.md` | who is writing, and the register | you, by hand |
| `pov.md` | positions held, and claims refused | you, by hand |
| `lexicon.json` | words in and out, each verified against real writing | you, by hand |
| `exemplars.jsonl` | real published pieces, one JSON object per line, `{"text": "...", "channel": "..."}` | you, once |
| `fingerprint.json` | measured bands computed FROM exemplars | `voiceloop fingerprint` only |
| `corrections.jsonl` | the loop: every delta between a draft and your rewrite | `voiceloop corrections add` only |

One writer per file. A file with two writers drifts, and you find out months
later from output nobody can explain.

`fingerprint.json` and `corrections.jsonl` are DERIVED or APPEND-ONLY. Editing
either by hand puts a number in your system that no measurement produced.
