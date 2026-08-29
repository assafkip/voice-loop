"""The loop's command line: log a correction, recompute the fingerprint, validate.

`corrections add` is the ONE writer for corrections.jsonl and the whole point of
this project. Every other voice tool learns from what you published. This learns
from the delta between what the model wrote and what you rewrote, which is the
only place your actual preferences are legible.

Append-only on purpose. A correction is a dated fact about what you wanted at a
moment, not a setting to be edited later. Superseding one means writing a newer
row, so the trail of how a voice changed stays readable.

WHY THIS FILE HAS ITS OWN TEST (from a real defect). Every module this imports is
generated from the engine; this file is not, so an engine signature can move and
leave the call sites here calling a shape that no longer exists. That is exactly
what happened: all three subcommands crashed on a clean checkout while the suite
stayed green, because nothing imported the command line. tests/test_cli.py runs
each subcommand end to end for that reason. Do not delete it as redundant.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys

from . import corpus, echo, fingerprint, slop_shapes, validate


def _now():
    """Injected in one place so a test can pin it. Never read twice per run."""
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def _corrections_add(args):
    today = _dt.date.today().isoformat()
    row = {
        "id": args.id or f"{today}-{args.slug}",
        "date": args.at or today,
        "quote": args.quote or "",
        "instruction": args.instruction,
        "scope": args.scope or [],
        "class": args.klass,
        "status": "active",
    }
    path = os.path.join(args.corpus_dir, corpus.CORRECTIONS)
    os.makedirs(args.corpus_dir, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"correction {row['id']} recorded; it rides in the next assembled prompt")
    return 0


def _fingerprint(args):
    voice = corpus.load(args.corpus_dir)
    # POST-KIND ONLY, and this is load-bearing (from a real defect). The freshness
    # check in validate.check_fingerprint_fresh hashes the post-kind corpus. A
    # fingerprint computed over every kind writes a different corpus_sha, so the
    # very next `validate` reports the file this command just wrote as stale. The
    # two selections have to be the same selection.
    texts = [r.get("text") or "" for r in voice.active_exemplars()
             if r.get("kind") == "post"]
    if not texts:
        print(f"no post-kind exemplars in {args.corpus_dir}/{corpus.EXEMPLARS}; "
              f"add your own writing before fingerprinting", flush=True)
        return 1
    doc = fingerprint.compute(texts, _now())
    out = os.path.join(args.corpus_dir, corpus.FINGERPRINT)
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(doc, handle, indent=1, sort_keys=True)
    os.replace(tmp, out)          # atomic: a half-written fingerprint is worse than none
    print(f"fingerprint written to {out} from {len(texts)} post-kind exemplar(s)")
    return 0



def _score(args):
    """Score ARBITRARY text against the corpus. The command that makes this
    usable from outside the repo that owns the corpus.

    why this exists (2026-08-29): every other subcommand acts on the corpus.
    There was no way to ask the one question a writer actually has, which is
    "does THIS draft read like me", without importing the package and wiring the
    calls by hand. So the engine was reachable only by people willing to write
    Python, and a draft written anywhere else went unchecked.

    Report, never a rewrite. It says which measured bands the draft falls outside
    and which deterministic gates it trips. It cannot say the draft is GOOD; a
    clean result means nothing is detectably wrong, which is a different claim and
    the README is explicit about the difference.
    """
    text = sys.stdin.read() if args.file == "-" else open(args.file, encoding="utf-8").read()
    if not text.strip():
        print("nothing to score: empty input", file=sys.stderr)
        return 2

    voice = corpus.load(args.corpus_dir)
    problems = []
    notes = []

    # 1. Style distance, only if a fingerprint exists. No fingerprint is a REASON,
    #    not a silent pass: without measured bands there is nothing to be far from.
    if voice.fingerprint is None:
        problems.append(("fingerprint", "no fingerprint.json; run `voiceloop fingerprint` "
                                        "to compute bands before scoring distance"))
    else:
        for metric in fingerprint.out_of_band(text, voice.fingerprint, tier="blocking"):
            detail = fingerprint.score(text, voice.fingerprint).get(metric, {})
            problems.append(("band", f"{metric}: {detail.get('value')} outside "
                                     f"{detail.get('band')}"))

    # 2. Templated shapes. Deterministic, corpus-independent.
    for hit in slop_shapes.check(text):
        problems.append(("shape", hit if isinstance(hit, str) else str(hit)))

    # 3. Verbatim reuse of the author's own exemplars. The text most likely to be
    #    echoed is the text the model was shown, which is why this is checked.
    exemplar_texts = [r.get("text") or "" for r in voice.active_exemplars()]
    if exemplar_texts:
        for hit in echo.prompt_echo(text, exemplar_texts) or []:
            problems.append(("echo", f"reuses corpus phrasing: {hit!r}"))

    # 4. Banned vocabulary, and an HONEST REPORT when there is none.
    #
    # This looks for a `negative` list, which is the schema corpus/lexicon.json
    # ships. A real corpus may key its lexicon differently, and when it does this
    # branch finds nothing and says so rather than staying quiet. Measured
    # 2026-08-29: a lexicon with keys `prefer`/`voiceprint_terms`/`contraction_pairs`
    # produced ZERO findings on "excited to announce a revolutionary, best in class
    # solution that will supercharge your workflow" -- text nobody would call
    # on-voice. A vocabulary check that silently checks nothing is worse than no
    # check, because the clean result reads as a pass.
    banned = (voice.lexicon or {}).get("negative") or []
    for word in banned:
        if re.search(rf"\b{re.escape(str(word))}\b", text, re.I):
            problems.append(("lexicon", f"banned term: {word!r}"))
    if not banned:
        notes.append("no `negative` list in lexicon.json, so VOCABULARY WAS NOT "
                     "CHECKED. Bands, shapes and echo were.")

    for kind, detail in problems:
        print(f"{kind}: {detail}")
    for note in notes:
        print(f"NOT CHECKED: {note}")
    print(f"{len(problems)} finding(s) against {len(exemplar_texts)} exemplar(s)")
    # A clean result means nothing DETECTABLE is wrong. Every check here is a NO
    # check; none of them can say the draft is good. The README says this too.
    return 1 if problems else 0


def _validate(args):
    # check_all returns a list of STRINGS and takes the corpus DIRECTORY. Both
    # halves of that were wrong here once; the shapes are asserted in test_cli.py.
    problems = validate.check_all(args.corpus_dir)
    for problem in problems:
        print(f"error: {problem}")
    print(f"{len(problems)} finding(s)")
    return 1 if problems else 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="voiceloop", description="the voice loop")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--corpus-dir", default=os.environ.get("VOICE_LOOP_CORPUS", "corpus"))
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("fingerprint", parents=[common],
                   help="recompute the measured bands from your exemplars")
    sub.add_parser("validate", parents=[common], help="check the corpus for problems")
    p_score = sub.add_parser("score", parents=[common],
                             help="score any text against your corpus")
    p_score.add_argument("file", nargs="?", default="-",
                         help="file to score, or - for stdin (default)")

    p_corr = sub.add_parser("corrections", help="the loop").add_subparsers(
        dest="subcmd", required=True)
    p_add = p_corr.add_parser("add", parents=[common],
                              help="log what you changed and why")
    p_add.add_argument("--instruction", required=True,
                       help="what the next draft should do differently")
    p_add.add_argument("--slug", required=True, help="kebab-case id suffix")
    p_add.add_argument("--quote", help="your own words, verbatim")
    p_add.add_argument("--scope", nargs="*", help="channels; empty means all")
    p_add.add_argument("--class", dest="klass", default="interpretive",
                       choices=["deterministic", "interpretive"])
    p_add.add_argument("--id")
    p_add.add_argument("--at")

    args = parser.parse_args(argv)
    if args.cmd == "fingerprint":
        return _fingerprint(args)
    if args.cmd == "score":
        return _score(args)
    if args.cmd == "validate":
        return _validate(args)
    if args.cmd == "corrections":
        return _corrections_add(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
