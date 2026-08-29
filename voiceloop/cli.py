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

from . import corpus, fingerprint, validate


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
    if args.cmd == "validate":
        return _validate(args)
    if args.cmd == "corrections":
        return _corrections_add(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
